import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V40", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V40")
st.markdown("### Configurazione Notti, Limiti e Incompatibilità")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR: CONFIGURAZIONE PERIODO ---
st.sidebar.header("📅 Selezione Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# --- 1. DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 4, "vincoli": ["No Pomeriggio", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 6, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 6, "vincoli": []},
        {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": False, "max_notti": 0, "vincoli": []}
    ]

# --- 2. INTERFACCIA INPUT ---
col_op, col_inc = st.columns([1.5, 1])

with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_editor_v40",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_editor_v40",
                            column_config={
                                "Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)
                            }, use_container_width=True)

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v40",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v40",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- FUNZIONI DI CONTROLLO ---
def check_incompatibili(nome, oggi_occupati, df_inc):
    for gia_in in oggi_occupati:
        match = df_inc[((df_inc['Op A'] == nome) & (df_inc['Op B'] == gia_in)) | 
                       ((df_inc['Op A'] == gia_in) & (df_inc['Op B'] == nome))]
        if not match.empty: return False
    return True

def get_giorni_vietati(nome, df_ass):
    vietati = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            d, a = int(r['Dal']), int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])
            for g in range(d, a + 1): vietati.add(g)
    return vietati

def check_vincoli_v40(nome, turno, is_we, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty: return True
    if turno == "N" and not row['fa_notti'].values[0]: return False
    v = [str(i).lower() for i in row['vincoli'].values[0]] if isinstance(row['vincoli'].values[0], list) else []
    if is_we and "no weekend" in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

# --- 3. LOGICA DI GENERAZIONE ---
def genera_v40(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_eff, notti_eff = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targets = {n: row['ore'] * 4 for n, row in op_df.set_index('nome').iterrows()}
    limiti_n = {n: row['max_notti'] for n, row in op_df.set_index('nome').iterrows()}
    stato_notte = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi_occupati = []

        # A. PREFERENZE
        for _, p in pref_df[pref_df['Giorno'] == g_num].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df):
                res_df.at[n, col] = t; oggi_occupati.append(n); ore_eff[n] += (9 if t=="N" else 7)
                if t=="N": {notti_eff.update({n: notti_eff[n]+1}), stato_notte.update({n: 1})}

        # B. SMONTO NOTTE
        for n in nomi:
            if stato_notte[n] == 1 and n not in oggi_occupati:
                res_df.at[n, col] = "N"; notti_eff[n] += 1; ore_eff[n] += 9; oggi_occupati.append(n); stato_notte[n] = 0

        # C. TURNI AUTO (N, M, P)
        for tipo, o_turno, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                cand = [n for n in nomi if n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df)]
                cand = [n for n in cand if check_vincoli_v40(n, tipo, is_we, op_df)]
                cand = [n for n in cand if check_incompatibili(n, oggi_occupati, inc_df)]
                if tipo == "N": cand = [n for n in cand if notti_eff[n] < limiti_n[n]]
                
                if not cand: break
                scelto = min(cand, key=lambda x: ore_eff[x]/targets[x] if targets[x]>0 else 0)
                res_df.at[scelto, col] = tipo; oggi_occupati.append(scelto); ore_eff[scelto] += o_turno
                if tipo == "N": {notti_eff.update({scelto: notti_eff[scelto]+1}), stato_notte.update({scelto: 1})}

    return res_df, ore_eff, targets, notti_eff

# --- 4. OUTPUT ---
if st.button("🚀 GENERA PIANO V40"):
    ris, ore, tar, notti = genera_v40(anno_scelto, mese_scelto_num)
    st.dataframe(ris, use_container_width=True)
    analisi = pd.DataFrame({"Notti": [notti[n] for n in ris.index], "Ore": [ore[n] for n in ris.index], "Sat %": [round((ore[n]/tar[n]*100) if tar[n]>0 else 0, 1) for n in ris.index]}, index=ris.index)
    st.table(analisi)
    st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name="Turni_V40.xlsx")
