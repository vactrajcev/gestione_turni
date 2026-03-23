import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V37", layout="wide")
st.title("🗓️ Generatore Turni V37 - Tabella Incompatibilità")

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
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "vincoli": []}
    ]

# --- 2. INTERFACCIA INPUT (TUTTO IN UNA PAGINA) ---
col_left, col_right = st.columns([1.5, 2])

with col_left:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v37",
                           column_config={
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

    st.subheader("🤝 Incompatibilità (Chi con chi NO)")
    # Tabella dedicata per definire le coppie che non devono lavorare insieme
    inc_df = st.data_editor(pd.DataFrame(columns=["Operatore A", "NON con Operatore B"]), num_rows="dynamic", key="inc_v37",
                            column_config={
                                "Operatore A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                "NON con Operatore B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)
                            }, use_container_width=True)

with col_right:
    col_ass, col_pref = st.columns(2)
    with col_ass:
        st.subheader("🚫 Assenze")
        ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v37",
                                column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
    with col_pref:
        st.subheader("⭐ Preferenze")
        pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v37",
                                 column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                                "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- LOGICHE DI CONTROLLO ---
def check_conflitto_coppia(nome, oggi_occupati, df_conflitti):
    for gia_in in oggi_occupati:
        # Controlla se esiste una riga nella tabella incompatibilità con questi due nomi
        match = df_conflitti[
            ((df_conflitti['Operatore A'] == nome) & (df_conflitti['NON con Operatore B'] == gia_in)) |
            ((df_conflitti['Operatore A'] == gia_in) & (df_conflitti['NON con Operatore B'] == nome))
        ]
        if not match.empty:
            return False
    return True

def get_giorni_vietati(nome, df_ass):
    vietati = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            d, a = int(r['Dal']), int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])
            for g in range(d, a + 1): vietati.add(g)
    return vietati

def check_vincoli(nome, turno, is_we, df_op):
    row = df_op[df_op['nome'] == nome]
    if row.empty: return True
    v = [str(i).lower() for i in row['vincoli'].values[0]] if isinstance(row['vincoli'].values[0], list) else []
    if is_we and "no weekend" in v: return False
    if turno == "N" and "fa notti" not in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

# --- 3. GENERATORE ---
def genera_v37(anno, mese):
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

        # A. PREFERENZE (Override totale)
        for _, p in pref_df[pref_df['Giorno'] == g_num].iterrows():
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

        # C. AUTOMATICI (N, M, P)
        for tipo, o_turno, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(tipo) < posti:
                cand = [n for n in nomi if n not in oggi_occupati and g_num not in get_giorni_vietati(n, ass_df)]
                cand = [n for n in cand if check_vincoli(n, tipo, is_we, op_df)]
                # CONTROLLO INCOMPATIBILITÀ DALLA TABELLA
                cand = [n for n in cand if check_conflitto_coppia(n, oggi_occupati, inc_df)]
                
                if not cand: break
                scelto = min(cand, key=lambda x: (ore_eff[x]/targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = tipo
                oggi_occupati.append(scelto)
                ore_eff[scelto] += o_turno
                if tipo == "N": {notti_cont.update({scelto: notti_cont[scelto]+1}), stato_notte.update({scelto: 1})}

    return res_df, ore_eff, targets, notti_cont

# --- 4. OUTPUT ---
if st.button("🚀 GENERA TURNI V37"):
    try:
        ris, ore, tar, notti = genera_v37(anno_scelto, mese_scelto_num)
        st.dataframe(ris, use_container_width=True)
        
        # Analisi Saturazione
        analisi = pd.DataFrame({
            "Notti": [notti[n] for n in ris.index], 
            "Ore": [ore[n] for n in ris.index], 
            "Target": [tar[n] for n in ris.index], 
            "Saturazione %": [round((ore[n]/tar[n]*100) if tar[n]>0 else 0, 1) for n in ris.index]
        }, index=ris.index)
        st.table(analisi)
        st.download_button("📥 Scarica Excel", data=to_excel(ris, analisi), file_name="Turni_V37.xlsx")
    except Exception as e:
        st.error(f"Errore: {e}")
