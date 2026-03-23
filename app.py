import streamlit as st
import pandas as pd
import random
import calendar

st.set_page_config(page_title="Gestione Turni 2-2-1", layout="wide")

st.title("🗓️ Generatore Turni Professionale")

# --- CONFIGURAZIONE ---
with st.sidebar:
    st.header("1. Impostazioni Mese")
    anno = st.number_input("Anno", 2024, 2030, 2026)
    mese = st.selectbox("Mese", list(range(1, 13)), index=3, format_func=lambda x: calendar.month_name[x])
    st.divider()
    st.header("2. Pesi Orari")
    h_m, h_p, h_n = 7, 8, 9 # Mattina 7h, Pom 8h, Notte 9h

# --- DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "vincoli": "No Pomeriggio, Fa Notti"},
        {"nome": "RISTOVA SIMONA (38)", "vincoli": "No Weekend, Solo Mattina"},
        {"nome": "CAMMARATA M. (38)", "vincoli": "Fa Notti"},
        {"nome": "MISELMI H. (38)", "vincoli": "Fa Notti"},
        {"nome": "SAKLI BESMA (38)", "vincoli": ""},
        {"nome": "BERTOLETTI B. (30)", "vincoli": ""},
        {"nome": "PALMIERI J. (28)", "vincoli": ""},
        {"nome": "MOSTACCHI M. (25)", "vincoli": ""}
    ]

st.subheader("👥 Lista Operatori")
df_op = pd.DataFrame(st.session_state.operatori)
edited_df = st.data_editor(df_op, num_rows="dynamic")

# --- LOGICA DI GENERAZIONE ---
if st.button("🚀 GENERA TABELLA TURNI"):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = []
    for g in range(1, num_giorni + 1):
        wd = calendar.weekday(anno, mese, g)
        giorni_cols.append(f"{g}-{calendar.day_name[wd][:3]}")

    nomi_op = edited_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op + ["ESTERNI"], columns=giorni_cols)

    def puo_lavorare(op, g_idx):
        if g_idx == 0: return True
        return res_df.iloc[list(res_df.index).index(op), g_idx-1] != "N"

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi_assegnati = []

        # --- 1. NOTTE (1 persona) ---
        candidati_n = edited_df[edited_df['vincoli'].str.contains("Fa Notti", na=False)]['nome'].tolist() + ["ESTERNI"]
        scelto_n = None
        # Blocco di 2 notti
        for d in candidati_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        if not scelto_n:
            disp_n = [d for d in candidati_n if puo_lavorare(d, g_idx)]
            scelto_n = random.choice(disp_n) if disp_n else "ESTERNI"
        res_df.at[scelto_n, col] = "N"
        oggi_assegnati.append(scelto_n)

        # --- 2. MATTINA (2 persone) ---
        m_count = 0
        # Simona priorità feriale
        if not is_we and puo_lavorare("RISTOVA SIMONA (38)", g_idx):
            res_df.at["RISTOVA SIMONA (38)", col] = "M"
            oggi_assegnati.append("RISTOVA SIMONA (38)")
            m_count += 1
        
        candidati_m = [d for d in nomi_op if d not in oggi_assegnati and puo_lavorare(d, g_idx)]
        candidati_m = [d for d in candidati_m if not (is_we and "RISTOVA" in d)]
        
        # Elena ha priorità in mattina perché non fa pomeriggi
        if "NERI ELENA (38)" in candidati_m and m_count < 2:
            res_df.at["NERI ELENA (38)", col] = "M"
            oggi_assegnati.append("NERI ELENA (38)")
            m_count += 1
            candidati_m.remove("NERI ELENA (38)")

        while m_count < 2 and candidati_m:
            s = random.choice(candidati_m)
            res_df.at[s, col] = "M"
            oggi_assegnati.append(s)
            candidati_m.remove(s)
            m_count += 1

        # --- 3. POMERIGGIO (2 persone) ---
        p_count = 0
        candidati_p = [d for d in nomi_op if d not in oggi_assegnati and puo_lavorare(d, g_idx)]
        # Filtro vincoli
        candidati_p = [d for d in candidati_p if "NERI" not in d and "RISTOVA" not in d]
        
        while p_count < 2 and candidati_p:
            s = random.choice(candidati_p)
            res_df.at[s, col] = "P"
            oggi_assegnati.append(s)
            candidati_p.remove(s)
            p_count += 1

    # --- CALCOLO ORE E CONTEGGI ---
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    
    st.write("### Tabella Risultante")
    st.dataframe(res_df)

    # Conteggi di controllo in fondo
    st.write("### Verifica Copertura (Deve essere 2-2-1)")
    controlli = pd.DataFrame({
        "Mattina (M)": [res_df[c].tolist().count("M") for c in giorni_cols],
        "Pomeriggio (P)": [res_df[c].tolist().count("P") for c in giorni_cols],
        "Notte (N)": [res_df[c].tolist().count("N") for c in giorni_cols]
    }, index=giorni_cols).T
    st.dataframe(controlli)

    st.download_button("📥 Scarica Turni", res_df.to_csv().encode('utf-8'), "turni.csv")
