import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V16", layout="wide")
st.title("🗓️ Generatore Turni Professionale (2-2-1)")

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

op_data = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

def genera_turni_stabili():
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    nomi = op_data['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    ore_effettive = {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_data.iterrows()}
    stato_notte = {n: 0 for n in nomi} # 0:libero, 1:fatta_prima_notte

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # --- A. COPERTURA NOTTE (1 Operatore) ---
        # Priorità a chi deve fare la seconda notte di fila
        percorso_notte = [n for n in nomi if stato_notte[n] == 1]
        for n in percorso_notte:
            res_df.at[n, col] = "N"
            stato_notte[n] = 0 # Ciclo finito
            oggi.append(n)
            ore_effettive[n] += 9

        # Se manca la notte, cerchiamo un nuovo notturnista
        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                v = str(op_data.set_index('nome').at[n, 'vincoli']).lower()
                if n not in oggi and "fa notti" in v:
                    if not (is_we and "no weekend" in v):
                        candidati_n.append(n)
            if candidati_n:
                scelto = min(candidati_n, key=lambda x: ore_effettive[x] / targets[x])
                res_df.at[scelto, col] = "N"
                stato_notte[scelto] = 1 # Segna per fare la seconda domani
                oggi.append(scelto)
                ore_effettive[scelto] += 9

        # --- B. COPERTURA DIURNI (2 Mattina + 2 Pomeriggio) ---
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            for _ in range(t_posti):
                candidati = []
                for n in nomi:
                    v = str(op_data.set_index('nome').at[n, 'vincoli']).lower()
                    if n not in oggi:
                        if is_we and "no weekend" in v: continue
                        if t_tipo == "M" and "solo pomeriggio" in v: continue
                        if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): continue
                        candidati.append(n)
                
                if candidati:
                    scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x])
                    res_df.at[scelto, col] = t_tipo
                    oggi.append(scelto)
                    ore_effettive[scelto] += t_ore

    return res_df, ore_effettive, targets

if st.button("🚀 GENERA TURNI SENZA ERRORI"):
    risultato, ore, targets = genera_turni_stabili()
    st.subheader("📅 Tabella Turni")
    st.dataframe(risultato)
    
    # Analisi Ore
    st.subheader("📊 Bilanciamento Ore")
    analisi = pd.DataFrame({
        "Ore Target": [targets[n] for n in risultato.index],
        "Ore Effettive": [ore[n] for n in risultato.index]
    }, index=risultato.index)
    analisi["%"] = (analisi["Ore Effettive"] / analisi["Ore Target"] * 100).round(1)
    st.table(analisi)

    # Verifica 2-2-1
    st.subheader("✅ Verifica Copertura")
    check = []
    for c in risultato.columns:
        l = risultato[c].tolist()
        check.append({"Giorno": c, "M": l.count("M"), "P": l.count("P"), "N": l.count("N")})
    st.write(pd.DataFrame(check).set_index("Giorno").T)
