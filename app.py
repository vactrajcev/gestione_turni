import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gestione Turni V31", layout="wide")
st.title("🗓️ Generatore Turni Professionale V31")

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

# --- 1. DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "vincoli": []}
    ]

# --- 2. INTERFACCIA INPUT ---
col_op, col_ass, col_pref = st.columns([1.2, 1, 1])

with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v31",
                           column_config={"vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"])})
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v31",
                            column_config={
                                "Operatore": st.column_config.SelectboxColumn("Operatore", options=lista_nomi),
                                "Dal": st.column_config.NumberColumn("Dal", min_value=1, max_value=31),
                                "Al": st.column_config.NumberColumn("Al", min_value=1, max_value=31)
                            })

with col_pref:
    st.subheader("⭐ Preferenze (Override)")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v31",
                             column_config={
                                 "Operatore": st.column_config.SelectboxColumn("Operatore", options=lista_nomi),
                                 "Giorno": st.column_config.NumberColumn("Giorno", min_value=1, max_value=31),
                                 "Turno": st.column_config.SelectboxColumn("Turno", options=["M", "P", "N"])
                             })

# --- FUNZIONI DI CONTROLLO ---
def get_giorni_vietati(nome, df_ass):
    vietati = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            d = int(r['Dal'])
            a = int(r['Al']) if pd.notna(r['Al']) else d
            for g in range(d, a + 1): vietati.add(g)
    return vietati

def check_vincoli_auto(nome, turno, is_we, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty: return True
    v_list = row['vincoli'].values[0]
    v = [str(i).lower() for i in v_list] if isinstance(v_list, list) else []
    
    if is_we and "no weekend" in v: return False
    if turno == "N" and "fa notti" not in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

# --- 3. LOGICA DI GENERAZIONE ---
def genera_v31(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_eff, notti_cont = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_df.iterrows()}
    stato_notte = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi_occupati = []

        # A. PREFERENZE (Override totale - Ignora vincoli)
        giorno_prefs = pref_df[pref_df['Giorno'] == g_num]
        for _, p in giorno_prefs.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df):
                res_df.at[n, col] = t
                oggi_occupati.append(n)
                ore_eff[n] += 9 if t=="N" else (7 if t=="M" else 8)
                if t=="N":
                    notti_cont[n] += 1
                    stato_notte[n] = 1

        # B. GESTIONE SMONTO NOTTE
        for n in nomi:
            if stato_notte[n] == 1 and n not in oggi_occupati:
                if g_num not in get_giorni_vietati(n, ass_df) and (g_num+1) not in get_giorni_vietati(n, ass_df):
                    res_df.at[n, col] = "N"
                    notti_cont[n] += 1; ore_eff[n] += 9; oggi_occupati.append(n)
                stato_notte[n] = 0

        # C. NOTTE AUTOMATICA (Con Vincoli)
        if res_df[col].tolist().count("N") < 1:
            cand = [n for n in nomi if n not in oggi_occupati and check_vincoli_auto(n, "N", is_we, op_df)]
            cand = [n for n in cand if g_num not in get_giorni_vietati(n, ass_df) and (g_num+1) not in get_giorni_vietati(n, ass_df)]
            if cand:
                s = min(cand, key=lambda x: (notti_cont[x], ore_eff[x]/targets[x] if targets[x]>0 else 0))
                res_df.at[s, col] = "N"; oggi_occupati.append(s); ore_eff[s] += 9; notti_cont[s] += 1; stato_notte[s] = 1

        # D. DIURNI AUTOMATICI (2M + 2P - Con Vincoli)
        for tipo, o_turno, posti in [("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                cand = [n for n in nomi if n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df) and check_vincoli_auto(n, tipo, is_we, op_df)]
                if not cand: break
                s = min(cand, key=lambda x: ore_eff[x]/targets[x] if targets[x]>0 else 0)
                res_df.at[s, col] = tipo; oggi_occupati.append(s); ore_eff[s] += o_turno

    return res_df, ore_eff, targets, notti_cont

# --- 4. OUTPUT ---
if st.button("🚀 GENERA E VERIFICA"):
    ris, ore, tar, notti = genera_v31(anno_scelto, mese_scelto_num)
    st.dataframe(ris, use_container_width=True)
    
    # Verifica 2-2-1
    st.subheader("✅ Copertura Giornaliera")
    c_data = [{"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")} for c in ris.columns]
    st.table(pd.DataFrame(c_data).set_index("G").T)
    
    # Analisi Saturazione
    st.subheader("📊 Saturazione Ore")
    analisi = pd.DataFrame({
        "Notti": [notti[n] for n in ris.index], 
        "Ore": [ore[n] for n in ris.index], 
        "Target": [tar[n] for n in ris.index], 
        "Saturazione %": [(ore[n]/tar[n]*100) if tar[n]>0 else 0 for n in ris.index]
    }, index=ris.index).round(1)
    st.table(analisi)
    
    st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name=f"Turni_{mese_scelto_nome}.xlsx")
