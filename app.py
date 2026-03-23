import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gestione Turni V26", layout="wide")
st.title("🗓️ Generatore Turni: Assenze + Preferenze + Excel")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR: PERIODO ---
st.sidebar.header("Configurazione Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Seleziona Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Seleziona Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1
num_giorni_mese = calendar.monthrange(anno_scelto, mese_scelto_num)[1]
lista_giorni_str = [f"{g}-{calendar.day_name[calendar.weekday(anno_scelto, mese_scelto_num, g)][:3]}" for g in range(1, num_giorni_mese + 1)]

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

# --- 2. INTERFACCIA DATI (3 COLONNE) ---
tab1, tab2, tab3 = st.columns(3)

with tab1:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v26")

with tab2:
    st.subheader("🚫 Assenze")
    periodi_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Dal_Giorno", "Al_Giorno"]),
        num_rows="dynamic", key="ass_v26",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Operatore", options=op_df['nome'].tolist()),
            "Dal_Giorno": st.column_config.NumberColumn("Dal", min_value=1, max_value=31),
            "Al_Giorno": st.column_config.NumberColumn("Al", min_value=1, max_value=31)
        }
    )

with tab3:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]),
        num_rows="dynamic", key="pref_v26",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Operatore", options=op_df['nome'].tolist()),
            "Giorno": st.column_config.SelectboxColumn("Giorno", options=range(1, 32)),
            "Turno": st.column_config.SelectboxColumn("Turno", options=["M", "P", "N"])
        }
    )

# --- FUNZIONI DI SUPPORTO ---
def get_giorni_vietati(nome, df_p):
    vietati = set()
    for _, r in df_p.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal_Giorno']):
            inizio = int(r['Dal_Giorno'])
            fine = int(r['Al_Giorno']) if pd.notna(r['Al_Giorno']) else inizio
            for g in range(inizio, fine + 1): vietati.add(g)
    return vietati

def get_preferenza(nome, giorno, df_pref):
    match = df_pref[(df_pref['Operatore'] == nome) & (df_pref['Giorno'] == giorno)]
    return match['Turno'].values[0] if not match.empty else None

# --- 3. LOGICA DI GENERAZIONE ---
def genera_v26(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_effettive = {n: 0 for n in nomi}
    conteggio_notti = {n: 0 for n in nomi} 
    targets = {row['nome']: row['ore'] * 4 for _, row in op_df.iterrows()}
    stato_notte = {n: 0 for n in nomi} 

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi = []

        # 0. INSERIMENTO PREFERENZE (Priorità massima)
        for n in nomi:
            pref = get_preferenza(n, g_num, pref_df)
            if pref and g_num not in get_giorni_vietati(n, periodi_df):
                res_df.at[n, col] = pref
                oggi.append(n)
                ore_effettive[n] += 9 if pref == "N" else (7 if pref == "M" else 8)
                if pref == "N": 
                    conteggio_notti[n] += 1
                    stato_notte[n] = 1 # Attiva il ciclo per domani

        # A. GESTIONE NOTTE (Proseguimento cicli)
        for n in nomi:
            if stato_notte[n] == 1 and n not in oggi:
                vietati = get_giorni_vietati(n, periodi_df)
                if g_num in vietati or (g_num + 1) in vietati:
                    stato_notte[n] = 0 
                    continue
                res_df.at[n, col] = "N"
                stato_notte[n] = 0
                oggi.append(n)
                ore_effettive[n] += 9
                conteggio_notti[n] += 1

        # Riempimento Notte (se manca)
        if res_df[col].tolist().count("N") < 1:
            candidati_n = [n for n in nomi if n not in oggi and "fa notti" in str(op_df[op_df['nome']==n]['vincoli']).lower() and g_num not in get_giorni_vietati(n, periodi_df)]
            candidati_n = [n for n in candidati_n if (g_num+1) not in get_giorni_vietati(n, periodi_df) and (g_num+2) not in get_giorni_vietati(n, periodi_df)]
            if candidati_n:
                scelto = min(candidati_n, key=lambda x: (conteggio_notti[x], ore_effettive[x]/targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = "N"; stato_notte[scelto] = 1; oggi.append(scelto)
                ore_effettive[scelto] += 9; conteggio_notti[scelto] += 1

        # B. DIURNI (Riempimento fino a 2M e 2P)
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            while res_df[col].tolist().count(t_tipo) < t_posti:
                candidati = [n for n in nomi if n not in oggi and g_num not in get_giorni_vietati(n, periodi_df)]
                if not candidati: break 
                scelto = min(candidati, key=lambda x: ore_effettive[x]/targets[x] if targets[x]>0 else 0)
                res_df.at[scelto, col] = t_tipo; oggi.append(scelto); ore_effettive[scelto] += t_ore

    return res_df, ore_effettive, targets, conteggio_notti

# --- 4. OUTPUT ---
if st.button(f"🚀 GENERA PER {mese_scelto_nome.upper()}"):
    risultato, ore, targets, notti = genera_v26(anno_scelto, mese_scelto_num)
    st.dataframe(risultato)
    
    # Analisi ed Excel
    analisi = pd.DataFrame({"Notti": [notti[n] for n in risultato.index], "Ore": [ore[n] for n in risultato.index]}, index=risultato.index)
    st.table(analisi)
    
    ex_data = to_excel(risultato, analisi)
    st.download_button("📥 Scarica Excel", data=ex_data, file_name="turni.xlsx")
