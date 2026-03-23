import streamlit as st
import pandas as pd
import random
import calendar
from datetime import datetime

st.set_page_config(page_title="Gestione Turni 2-2-1", layout="wide")

st.title("🗓️ Generatore Turni Professionale")
st.markdown("Configura i parametri e genera la tabella per il mese selezionato.")

# --- SIDEBAR: CONFIGURAZIONE ---
with st.sidebar:
    st.header("Impostazioni Mese")
    anno = st.number_input("Anno", 2024, 2030, 2026)
    mese = st.selectbox("Mese", list(range(1, 13)), index=3, format_func=lambda x: calendar.month_name[x])
    
    st.divider()
    st.header("Parametri Orari")
    h_m = st.number_input("Ore Mattina (07-14)", value=7)
    h_p = st.number_input("Ore Pomeriggio (14-22)", value=8)
    h_n = st.number_input("Ore Notte (22-07)", value=9)

# --- OPERATORI ---
st.subheader("👥 Gestione Operatori e Contratti")
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore": 28, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore": 25, "vincoli": []}
    ]

# Tabella editabile per i nomi e ore
df_op = pd.DataFrame(st.session_state.operatori)
edited_df = st.data_editor(df_op, num_rows="dynamic")

# --- LOGICA DI GENERAZIONE ---
if st.button("🚀 GENERA TURNI APRILE"):
    num_giorni = calendar.monthrange(anno, mese)[1]
    nomi_giorni = []
    for g in range(1, num_giorni + 1):
        wd = calendar.weekday(anno, mese, g)
        nomi_giorni.append(f"{g}-{calendar.day_name[wd][:3]}")

    nomi_op = edited_df['nome'].tolist()
    turni_df = pd.DataFrame("-", index=nomi_op + ["ESTERNI"], columns=nomi_giorni)
    ore_cumulate = {n: 0 for n in nomi_op}
    ore_cumulate["ESTERNI"] = 0

    for idx, col in enumerate(nomi_giorni):
        is_we = "Sat" in col or "Sun" in col
        oggi = []

        # 1. NOTTE (1 persona)
        candidati_n = edited_df[edited_df['vincoli'].apply(lambda x: "Fa Notti" in x)]['nome'].tolist() + ["ESTERNI"]
        scelto_n = None
        for d in candidati_n:
            if idx > 0 and turni_df.at[d, nomi_giorni[idx-1]] == "N" and (idx == 1 or turni_df.at[d, nomi_giorni[idx-2]] != "N"):
                scelto_n = d
        if not scelto_n:
            disp = [d for d in candidati_n if (idx == 0 or turni_df.at[d, nomi_giorni[idx-1]] != "N")]
            scelto_n = random.choice(disp) if disp else "ESTERNI"
        turni_df.at[scelto_n, col] = "N"; ore_cumulate[scelto_n] += h_n; oggi.append(scelto_n)

        # 2. MATTINA (2 persone)
        # Logica semplificata per l'esempio app
        candidati_m = [d for d in nomi_op if d not in oggi and (idx == 0 or turni_df.at[d, nomi_giorni[idx-1]] != "N")]
        for d in candidati_m[:2]:
            turni_df.at[d, col] = "M"; ore_cumulate[d] += h_m; oggi.append(d)

        # 3. POMERIGGIO (2 persone)
        candidati_p = [d for d in nomi_op if d not in oggi and (idx == 0 or turni_df.at[d, nomi_giorni[idx-1]] != "N")]
        for d in candidati_p[:2]:
            turni_df.at[d, col] = "P"; ore_cumulate[d] += h_p

    # Totali
    turni_df["TOT ORE"] = turni_df.apply(lambda r: sum([h_m if x=='M' else h_p if x=='P' else h_n if x=='N' else 0 for x in r]), axis=1)
    
    st.success("Tabella Generata!")
    st.dataframe(turni_df)
    
    csv = turni_df.to_csv().encode('utf-8')
    st.download_button("📥 Scarica Excel (CSV)", data=csv, file_name=f"turni_{mese}_{anno}.csv")
