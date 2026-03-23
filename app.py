import streamlit as st
import pandas as pd
import random
import calendar

st.set_page_config(page_title="Gestione Turni 2-2-1", layout="wide")

st.title("🗓️ Generatore Turni Professionale")

# --- DATABASE OPERATORI DI DEFAULT ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore_contratto": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore_contratto": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore_contratto": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore_contratto": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore_contratto": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore_contratto": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore_contratto": 25, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore_contratto": 25, "vincoli": []}
    ]

st.subheader("👥 Lista Operatori")
# Editor tabella con opzioni fisse per i vincoli
opzioni_vincoli = ["No Pomeriggio", "Fa Notti", "No Weekend", "Solo Mattina"]
df_op_input = pd.DataFrame(st.session_state.operatori)
edited_df = st.data_editor(df_op_input, num_rows="dynamic")

# Funzione di supporto per pulire i vincoli ed evitare errori di tipo
def ha_vincolo(riga_op, testo_vincolo):
    v = riga_op.get('vincoli', [])
    if isinstance(v, list):
        return testo_vincolo in v
    return False

# --- LOGICA DI GENERAZIONE ---
if st.button("🚀 GENERA TABELLA TURNI"):
    anno, mese = 2026, 4 # Aprile 2026 come da tua richiesta
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = []
    for g in range(1, num_giorni + 1):
        wd = calendar.weekday(anno, mese, g)
        giorni_cols.append(f"{g}-{calendar.day_name[wd][:3]}")

    nomi_op = edited_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op + ["ESTERNI"], columns=giorni_cols)

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi_assegnati = []

        # 1. NOTTE (1 PERSONA) - 9 ore
        candidati_n = [r['nome'] for _, r in edited_df.iterrows() if ha_vincolo(r, "Fa Notti")] + ["ESTERNI"]
        scelto_n = None
        # Blocco di 2 notti
        for d in candidati_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        if not scelto_n:
            disp_n = [d for d in candidati_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            scelto_n = random.choice(disp_n) if disp_n else "ESTERNI"
        res_df.at[scelto_n, col] = "N"
        oggi_assegnati.append(scelto_n)

        # 2. MATTINA (2 PERSONE) - 7 ore
        m_count = 0
        cand_m_base = []
        for _, r in edited_df.iterrows():
            nome = r['nome']
            if nome in oggi_assegnati: continue
            if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": continue # Smonto notte
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_m_base.append(nome)
        
        while m_count < 2 and cand_m_base:
            s = random.choice(cand_m_base)
            res_df.at[s, col] = "M"
            oggi_assegnati.append(s)
            cand_m_base.remove(s)
            m_count += 1

        # 3. POMERIGGIO (2 PERSONE) - 8 ore
        p_count = 0
        cand_p_base = []
        for _, r in edited_df.iterrows():
            nome = r['nome']
            if nome in oggi_assegnati: continue
            if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": continue
            if ha_vincolo(r, "No Pomeriggio") or ha_vincolo(r, "Solo Mattina"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_p_base.append(nome)

        while p_count < 2 and cand_p_base:
            s = random.choice(cand_p_base)
            res_df.at[s, col] = "P"
            oggi_assegnati.append(s)
            cand_p_base.remove(s)
            p_count += 1

    # --- CALCOLO ORE FINALI ---
    def calcola_riga(r):
        return (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9)
    
    res_df["ORE TOT"] = res_df.apply(calcola_riga, axis=1)

    st.write("### 📅 Tabella Turni Generata")
    st.dataframe(res_df)

    # --- CONTEGGI DI CONTROLLO RIGIDI ---
    st.write("### ✅ Verifica Copertura (Deve essere sempre 2-2-1)")
    check_data = {
        "Mattina (M)": [res_df[c].tolist().count("M") for c in giorni_cols],
        "Pomeriggio (P)": [res_df[c].tolist().count("P") for c in giorni_cols],
        "Notte (N)": [res_df[c].tolist().count("N") for c in giorni_cols]
    }
    st.table(pd.DataFrame(check_data, index=giorni_cols).T)

    st.download_button("📥 Scarica Excel", res_df.to_csv().encode('utf-8'), "turni_aprile.csv")
