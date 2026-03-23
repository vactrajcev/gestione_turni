import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V11", layout="wide")
st.title("🗓️ Generatore Turni: Algoritmo a Rotazione Sfalsata")

# Database Operatori (Invariato)
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

edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Solo Notti", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"])
    },
    key="editor_v11"
)

def calcola_punteggio_equo(op, tipo_turno, is_weekend, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in op.get('vincoli', [])]
    nome = op['nome']
    target_mensile = op.get('ore', 0) * 4
    
    # --- LOGICA DI SFALSAMENTO (Sequenza N-N-S-R) ---
    if g_idx > 0:
        ieri = res_df.at[nome, giorni_cols[g_idx-1]]
        # Se ieri ha fatto la prima notte del mese o di una sequenza, oggi DEVE fare la seconda
        if ieri == "N":
            if g_idx > 1 and res_df.at[nome, giorni_cols[g_idx-2]] == "N":
                return 999999 # Già fatte 2, oggi SMONTO
            return 0 if tipo_turno == "N" else 999999
        
        # Se l'altro ieri ha finito le 2 notti, oggi è riposo obbligatorio
        if g_idx > 1 and res_df.at[nome, giorni_cols[g_idx-2]] == "N":
             return 999999 

    # --- VINCOLI RIGIDI ---
    if is_weekend and "no weekend" in v: return 999999
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return 999999
    if "solo mattina" in v and tipo_turno != "M": return 999999
    
    # --- BILANCIAMENTO ORE ---
    saturazione = ore_tot_mese / target_mensile if target_mensile > 0 else 0
    punteggio = saturazione * 1000
    
    # Se iniziamo il mese (g_idx < 3), diamo un piccolo bonus casuale per sfalsare le partenze
    if g_idx < 3:
        import random
        punteggio += random.randint(0, 50)

    return punteggio

if st.button("🚀 GENERA CON SFALSAMENTO INIZIALE"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna()].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # 1. ASSEGNAZIONE NOTTE (Priorità assoluta per creare lo sfalsamento)
        for turno, ore_t, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            candidati = []
            for _, op in op_validi.iterrows():
                if op['nome'] not in oggi:
                    score = calcola_punteggio_equo(op, turno, is_we, ore_tot_mese[op['nome']], g_idx, res_df, giorni_cols)
                    if score < 900000:
                        candidati.append((op['nome'], score))
            
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    # --- RISULTATI ---
    st.subheader("📅 Tabella Turni (Sfalsata)")
    st.dataframe(res_df)
    
    # Verifica Copertura (Tabella Orizzontale per leggibilità)
    st.subheader("✅ Verifica Copertura 2-2-1")
    conteggi = []
    for c in giorni_cols:
        l = res_df[c].tolist()
        conteggi.append({"Giorno": c, "M": l.count("M"), "P": l.count("P"), "N": l.count("N")})
    st.write(pd.DataFrame(conteggi).set_index("Giorno").T)

    # Analisi Ore
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.subheader("📊 Analisi Carico")
    analisi = pd.DataFrame({
        "Target": op_validi.set_index('nome')['ore'] * 4,
        "Effettive": res_df["ORE TOT"]
    })
    analisi["% Sat."] = (analisi["Effettive"] / analisi["Target"] * 100).round(1)
    st.table(analisi.sort_values("% Sat."))
