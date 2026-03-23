import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gestione Turni V21", layout="wide")
st.title("🗓️ Generatore Turni Professionale")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df, mese_nome, anno):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR PER SELEZIONE PERIODO ---
st.sidebar.header("Configurazione Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# Default al mese corrente
mese_scelto_nome = st.sidebar.selectbox("Seleziona Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Seleziona Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# 1. DATABASE OPERATORI
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

st.subheader(f"Configurazione Operatori per {mese_scelto_nome} {anno_scelto}")
op_data = st.data_editor(
    pd.DataFrame(st.session_state.operatori), 
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli",
            options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"]
        )
    }
)
 
def genera_turni_equi(anno, mese):
    num_giorni = calendar.monthrange(anno, mese)[1]
    # Nomi dei giorni in italiano/inglese abbreviato
    giorni_cols = []
    for g in range(1, num_giorni + 1):
        nome_giorno = calendar.day_name[calendar.weekday(anno, mese, g)][:3]
        giorni_cols.append(f"{g}-{nome_giorno}")
    
    nomi = op_data['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_effettive = {n: 0 for n in nomi}
    conteggio_notti = {n: 0 for n in nomi} 
    targets = {row['nome']: row['ore'] * 4 for _, row in op_data.iterrows()}
    stato_notte = {n: 0 for n in nomi} 

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # --- A. COPERTURA NOTTE (EQUA) ---
        for n in nomi:
            if stato_notte[n] == 1:
                res_df.at[n, col] = "N"
                stato_notte[n] = 0
                oggi.append(n)
                ore_effettive[n] += 9
                conteggio_notti[n] += 1

        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                v_row = op_data[op_data['nome'] == n]['vincoli'].values[0]
                v = str(v_row).lower()
                if n not in oggi and "fa notti" in v:
                    if not (is_we and "no weekend" in v):
                        candidati_n.append(n)
            
            if candidati_n:
                scelto = min(candidati_n, key=lambda x: (conteggio_notti[x], ore_effettive[x] / targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = "N"
                stato_notte[scelto] = 1 
                oggi.append(scelto)
                ore_effettive[scelto] += 9
                conteggio_notti[scelto] += 1

        # --- B. COPERTURA DIURNI (2M + 2P) ---
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_assegnati = 0
            while posti_assegnati < t_posti:
                candidati = []
                for n in nomi:
                    v_row = op_data[op_data['nome'] == n]['vincoli'].values[0]
                    v = str(v_row).lower()
                    if n not in oggi:
                        if is_we and "no weekend" in v: continue
                        if t_tipo == "M" and "solo pomeriggio" in v: continue
                        if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): continue
                        candidati.append(n)
                if not candidati: break 
                scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x] if targets[x]>0 else 0)
                res_df.at[scelto, col] = t_tipo
                oggi.append(scelto)
                ore_effettive[scelto] += t_ore
                posti_assegnati += 1

    return res_df, ore_effettive, targets, conteggio_notti

if st.button(f"🚀 GENERA TURNI PER {mese_scelto_nome.upper()}"):
    risultato, ore, targets, notti = genera_turni_equi(anno_scelto, mese_scelto_num)
    
    st.subheader(f"📅 Tabella Turni - {mese_scelto_nome} {anno_scelto}")
    st.dataframe(risultato)
    
    st.subheader("📊 Analisi Carico")
    analisi = pd.DataFrame({
        "Notti Totali": [notti[n] for n in risultato.index],
        "Ore Totali": [ore[n] for n in risultato.index],
        "Target": [targets[n] for n in risultato.index],
        "% Saturazione": [(ore[n] / targets[n] * 100) if targets[n]>0 else 0 for n in risultato.index]
    }, index=risultato.index)
    st.table(analisi.round(1))

    # Verifica Copertura 2-2-1
    check = [{"G": c.split("-")[0], "M": risultato[c].tolist().count("M"), "P": risultato[c].tolist().count("P"), "N": risultato[c].tolist().count("N")} for c in risultato.columns]
    st.write("**Verifica Copertura Giornaliera:**")
    st.table(pd.DataFrame(check).set_index("G").T)

    # Download Excel
    excel_data = to_excel(risultato, analisi, mese_scelto_nome, anno_scelto)
    st.download_button(
        label=f"📥 Scarica Excel {mese_scelto_nome}",
        data=excel_data,
        file_name=f"turni_{mese_scelto_nome}_{anno_scelto}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
