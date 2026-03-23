import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gestione Turni Pro V33", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V33")
st.markdown("### Vincoli, Incompatibilità e Priorità")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR ---
st.sidebar.header("📅 Configurazione")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# --- 1. DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "priorita": 1, "incompatibile_con": []},
        {"nome": "RISTOVA SIMONA", "ore": 38, "priorita": 1, "incompatibile_con": []},
        {"nome": "CAMMARATA M.", "ore": 38, "priorita": 1, "incompatibile_con": []},
        {"nome": "MISELMI H.", "ore": 38, "priorita": 1, "incompatibile_con": []},
        {"nome": "SAKLI BESMA", "ore": 38, "priorita": 1, "incompatibile_con": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "priorita": 1, "incompatibile_con": []},
        {"nome": "PALMIERI J.", "ore": 25, "priorita": 1, "incompatibile_con": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "priorita": 1, "incompatibile_con": []}
    ]

# --- 2. INTERFACCIA INPUT ---
tab_op, tab_regole = st.tabs(["👥 Anagrafica Operatori", "⚙️ Regole, Assenze e Preferenze"])

with tab_op:
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_ed_v33",
                           column_config={
                               "priorita": st.column_config.NumberColumn("Priorità (1-5)", min_value=1, max_value=5, help="5 = Massima priorità nel ricevere turni"),
                               "incompatibile_con": st.column_config.MultiselectColumn("Mai in turno con:", options=pd.DataFrame(st.session_state.operatori)['nome'].tolist())
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with tab_regole:
    col_ass, col_pref = st.columns(2)
    with col_ass:
        st.subheader("🚫 Assenze")
        ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v33",
                                column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
    with col_pref:
        st.subheader("⭐ Preferenze")
        pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v33",
                                 column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                                "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- FUNZIONI DI LOGICA ---
def get_giorni_vietati(nome, df_ass):
    vietati = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            d, a = int(r['Dal']), int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])
            for g in range(d, a + 1): vietati.add(g)
    return vietati

def check_incompatibilita(nome, oggi_occupati, df_op):
    """Verifica se il candidato può lavorare con chi è già in turno oggi"""
    incomp_row = df_op[df_op['nome'] == nome]['incompatibile_con'].values[0]
    if not isinstance(incomp_row, list): return True
    for gia_in_turno in oggi_occupati:
        if gia_in_turno in incomp_row: return False # L'operatore B è nella lista nera di A
    
    # Controllo inverso: qualcuno già in turno ha il candidato nella sua lista nera?
    for gia_in_turno in oggi_occupati:
        list_nera_altro = df_op[df_op['nome'] == gia_in_turno]['incompatibile_con'].values[0]
        if isinstance(list_nera_altro, list) and nome in list_nera_altro: return False
    return True

# --- 3. CORE GENERATOR ---
def genera_v33(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_eff, notti_cont = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_df.iterrows()}
    priorita_map = {row['nome']: row['priorita'] for _, row in op_df.iterrows()}
    stato_notte = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        oggi_occupati = []

        # A. PREFERENZE (Sempre prime)
        g_prefs = pref_df[pref_df['Giorno'] == g_num]
        for _, p in g_prefs.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df):
                res_df.at[n, col] = t
                oggi_occupati.append(n)
                ore_eff[n] += 9 if t=="N" else (7 if t=="M" else 8)
                if t=="N": {notti_cont.update({n: notti_cont[n]+1}), stato_notte.update({n: 1})}

        # B. SMONTO NOTTE
        for n in nomi:
            if stato_notte[n] == 1 and n not in oggi_occupati:
                res_df.at[n, col] = "N"
                notti_cont[n] += 1; ore_eff[n] += 9; oggi_occupati.append(n)
                stato_notte[n] = 0

        # C. TURNI AUTOMATICI (Notte, poi M, poi P)
        for tipo, o_turno, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                # Candidati validi: non occupati, non in ferie, compatibili con chi è già in turno
                cand = [n for n in nomi if n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df)]
                cand = [n for n in cand if check_incompatibilita(n, oggi_occupati, op_df)]
                
                # Se è notte, controllo protezione smonto domani (pref diurne)
                if tipo == "N":
                    cand = [n for n in cand if (g_num+1) not in get_giorni_vietati(n, ass_df)]
                
                if not cand: break

                # SCELTA INTELLIGENTE: 
                # 1. Priorità alta vince 
                # 2. A parità di priorità, chi ha meno ore (saturazione) vince
                scelto = max(cand, key=lambda x: (priorita_map[x], - (ore_eff[x]/targets[x] if targets[x]>0 else 0)))
                
                res_df.at[scelto, col] = tipo
                oggi_occupati.append(scelto)
                ore_eff[scelto] += o_turno
                if tipo == "N": {notti_cont.update({scelto: notti_cont[scelto]+1}), stato_notte.update({scelto: 1})}

    return res_df, ore_eff, targets, notti_cont

# --- 4. OUTPUT ---
if st.button("🚀 GENERA PIANO V33"):
    ris, ore, tar, notti = genera_v33(anno_scelto, mese_scelto_num)
    st.dataframe(ris, use_container_width=True)
    
    # Riepilogo 2-2-1
    c_data = [{"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")} for c in ris.columns]
    st.table(pd.DataFrame(c_data).set_index("G").T)
    
    # Analisi
    analisi = pd.DataFrame({"Notti": [notti[n] for n in ris.index], "Ore": [ore[n] for n in ris.index], "Saturazione %": [(ore[n]/tar[n]*100) if tar[n]>0 else 0 for n in ris.index]}, index=ris.index).round(1)
    st.table(analisi)
    st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name="Turni_V33.xlsx")
