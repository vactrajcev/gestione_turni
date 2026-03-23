import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V36", layout="wide")
st.title("🗓️ Generatore Turni Professionale - V36")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR: CONFIGURAZIONE PERIODO ---
st.sidebar.header("📅 Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# --- 1. DATABASE INIZIALE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "priorita": 3, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"], "incompatibile_con": []},
        {"nome": "RISTOVA SIMONA", "ore": 38, "priorita": 5, "vincoli": ["No Weekend", "Solo Mattina"], "incompatibile_con": []},
        {"nome": "CAMMARATA M.", "ore": 38, "priorita": 2, "vincoli": ["Fa Notti"], "incompatibile_con": []},
        {"nome": "MISELMI H.", "ore": 38, "priorita": 2, "vincoli": ["Fa Notti"], "incompatibile_con": []},
        {"nome": "SAKLI BESMA", "ore": 38, "priorita": 1, "vincoli": [], "incompatibile_con": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "priorita": 1, "vincoli": [], "incompatibile_con": []},
        {"nome": "PALMIERI J.", "ore": 25, "priorita": 1, "vincoli": [], "incompatibile_con": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "priorita": 1, "vincoli": [], "incompatibile_con": []}
    ]

# --- 2. INTERFACCIA UNICA PAGINA ---
col_op, col_ass, col_pref = st.columns([1.5, 1, 1])

with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v36",
                           column_config={
                               "priorita": st.column_config.NumberColumn("Prio", min_value=1, max_value=5, default=1),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"]),
                               "incompatibile_con": st.column_config.MultiselectColumn("MAI con", options=[o['nome'] for o in st.session_state.operatori])
                           })
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v36",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})

with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v36",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- LOGICA DI CONTROLLO ---
def check_vincoli_auto(nome, turno, is_we, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty: return True
    v_list = row['vincoli'].values[0] if 'vincoli' in row.columns else []
    v = [str(i).lower() for i in v_list] if isinstance(v_list, list) else []
    if is_we and "no weekend" in v: return False
    if turno == "N" and "fa notti" not in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

def check_incompatibilita(nome, oggi_occupati, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty or 'incompatibile_con' not in df_op.columns: return True
    incomp = row['incompatibile_con'].values[0] if isinstance(row['incompatibile_con'].values[0], list) else []
    for gia_in in oggi_occupati:
        if gia_in in incomp: return False
        row_altro = df_op[df_op['nome'] == gia_in]
        inc_altro = row_altro['incompatibile_con'].values[0] if 'incompatibile_con' in row_altro.columns else []
        if isinstance(inc_altro, list) and nome in inc_altro: return False
    return True

def get_giorni_vietati(nome, df_ass):
    vietati = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            d, a = int(r['Dal']), int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])
            for g in range(d, a + 1): vietati.add(g)
    return vietati

def ha_pref_diurna_domani(nome, g_oggi, df_pref):
    match = df_pref[(df_pref['Operatore'] == nome) & (df_pref['Giorno'] == g_oggi + 1)]
    return not match.empty and match['Turno'].values[0] in ["M", "P"]

# --- 3. GENERATORE ---
def genera_v36(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_eff, notti_cont = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targets = {n: row.get('ore', 38) * 4 for n, row in op_df.set_index('nome').iterrows()}
    prio_map = {n: row.get('priorita', 1) for n, row in op_df.set_index('nome').iterrows()}
    stato_notte = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi_occupati = []

        # A. PREFERENZE (Senza vincoli, ma rispetta incompatibilità se inserite qui)
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
                res_df.at[n, col] = "N"; notti_cont[n] += 1; ore_eff[n] += 9; oggi_occupati.append(n); stato_notte[n] = 0

        # C. TURNI AUTOMATICI (N, M, P)
        for tipo, o_turno, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                cand = [n for n in nomi if n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df)]
                cand = [n for n in cand if check_vincoli_auto(n, tipo, is_we, op_df)]
                cand = [n for n in cand if check_incompatibilita(n, oggi_occupati, op_df)]
                if tipo == "N": cand = [n for n in cand if not ha_pref_diurna_domani(n, g_num, pref_df)]
                
                if not cand: break
                scelto = max(cand, key=lambda x: (prio_map.get(x, 1), - (ore_eff[x]/targets[x] if targets[x]>0 else 0)))
                res_df.at[scelto, col] = tipo
                oggi_occupati.append(scelto)
                ore_eff[scelto] += o_turno
                if tipo == "N": {notti_cont.update({scelto: notti_cont[scelto]+1}), stato_notte.update({scelto: 1})}

    return res_df, ore_eff, targets, notti_cont

# --- 4. ESECUZIONE ---
if st.button("🚀 GENERA E VERIFICA"):
    try:
        ris, ore, tar, notti = genera_v36(anno_scelto, mese_scelto_num)
        st.dataframe(ris, use_container_width=True)
        
        # Copertura
        c_data = [{"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")} for c in ris.columns]
        st.write("**Copertura Giornaliera:**")
        st.table(pd.DataFrame(c_data).set_index("G").T)
        
        # Analisi
        analisi = pd.DataFrame({"Notti": [notti[n] for n in ris.index], "Ore": [ore[n] for n in ris.index], "Saturazione %": [round((ore[n]/tar[n]*100) if tar[n]>0 else 0, 1) for n in ris.index]}, index=ris.index)
        st.table(analisi)
        st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name=f"Turni_{mese_scelto_nome}.xlsx")
    except Exception as e:
        st.error(f"Si è verificato un errore: {e}. Controlla che i nomi nelle tabelle siano corretti.")
