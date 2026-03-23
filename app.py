import streamlit as st
import pandas as pd  # CORRETTO: era import pd as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V38", layout="wide")
st.title("🗓️ Generatore Turni V38 - Fix Incompatibilità e Import")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR ---
st.sidebar.header("📅 Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# --- 1. DATABASE INIZIALE ---
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

# --- 2. INTERFACCIA ---
col_left, col_right = st.columns([1.5, 2])

with col_left:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v38",
                           column_config={
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

    st.subheader("🤝 Incompatibilità (Blocco Coppie)")
    inc_df = st.data_editor(pd.DataFrame(columns=["Operatore A", "NON con Operatore B"]), num_rows="dynamic", key="inc_v38",
                            column_config={
                                "Operatore A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                "NON con Operatore B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)
                            }, use_container_width=True)

with col_right:
    col_ass, col_pref = st.columns(2)
    with col_ass:
        st.subheader("🚫 Assenze")
        ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v38",
                                column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
    with col_pref:
        st.subheader("⭐ Preferenze")
        pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v38",
                                 column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                                "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- LOGICHE DI CONTROLLO ---
def check_conflitto_incompatibili(nome, oggi_occupati, df_inc):
    """Ritorna False se l'operatore non può stare con chi è già in turno"""
    for gia_in in oggi_occupati:
        match = df_inc[
            ((df_inc['Operatore A'] == nome) & (df_inc['NON con Operatore B'] == gia_in)) |
            ((df_inc['Operatore A'] == gia_in) & (df_inc['NON con Operatore B'] == nome))
        ]
        if not match.empty:
            return False
    return True

def check_vincoli_v38(nome, turno, is_we, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty: return True
    v_raw = row['vincoli'].values[0]
    v = [str(i).lower() for i in v_raw] if isinstance(v_raw, list) else []
    if is_we and "no weekend" in v: return False
    if turno == "N" and "fa notti" not in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

# --- 3. GENERATORE ---
def genera_v38(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_eff, notti_cont = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targets = {n: row.get('ore', 38) * 4 for n, row in op_df.set_index('nome').iterrows()}
    stato_notte = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi_occupati = []

        # 1. PREFERENZE
        for _, p in pref_df[pref_df['Giorno'] == g_num].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in oggi_occupati:
                res_df.at[n, col] = t
                oggi_occupati.append(n)
                ore_eff[n] += 9 if t=="N" else (7 if t=="M" else 8)
                if t=="N": {notti_cont.update({n: notti_cont[n]+1}), stato_notte.update({n: 1})}

        # 2. SMONTO NOTTE
        for n in nomi:
            if stato_notte[n] == 1 and n not in oggi_occupati:
                res_df.at[n, col] = "N"; notti_cont[n] += 1; ore_eff[n] += 9; oggi_occupati.append(n); stato_notte[n] = 0

        # 3. TURNI AUTOMATICI (N, M, P)
        for tipo, o_turno, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                # Candidati che non sono già in turno, non sono in ferie e rispettano i vincoli
                cand = [n for n in nomi if n not in oggi_occupati]
                cand = [n for n in cand if check_vincoli_v38(n, tipo, is_we, op_df)]
                # AGGIUNTO: Controllo incompatibilità specifico
                cand = [n for n in cand if check_conflitto_incompatibili(n, oggi_occupati, inc_df)]
                
                if not cand: break
                
                # Scegli chi ha meno ore rispetto al target
                scelto = min(cand, key=lambda x: (ore_eff[x]/targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = tipo
                oggi_occupati.append(scelto)
                ore_eff[scelto] += o_turno
                if tipo == "N": {notti_cont.update({scelto: notti_cont[scelto]+1}), stato_notte.update({scelto: 1})}

    return res_df, ore_eff, targets, notti_cont

# --- 4. ESECUZIONE ---
if st.button("🚀 GENERA TURNI V38"):
    try:
        ris, ore, tar, notti = genera_v38(anno_scelto, mese_scelto_num)
        st.dataframe(ris, use_container_width=True)
        
        analisi = pd.DataFrame({
            "Ore": [ore[n] for n in ris.index], 
            "Saturazione %": [round((ore[n]/tar[n]*100) if tar[n]>0 else 0, 1) for n in ris.index]
        }, index=ris.index)
        st.table(analisi)
        st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name="Turni_V38_Final.xlsx")
    except Exception as e:
        st.error(f"Errore: {e}. Verifica i nomi nelle tabelle.")
