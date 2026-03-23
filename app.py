import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni Equa V8", layout="wide")
st.title("🗓️ Generatore Turni con Saturazione Armonizzata")

if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti"]},
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
    key="editor_v8"
)

def calcola_punteggio_equo(op, tipo_turno, is_weekend, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in op.get('vincoli', [])] if isinstance(op.get('vincoli'), list) else []
    nome = op['nome']
    target_mensile = op.get('ore', 0) * 4
    
    # --- 1. REGOLE RIGIDE ---
    if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": return 999999 # Smonto
    if g_idx > 1 and res_df.at[nome, giorni_cols[g_idx-2]] == "N": return 999999 # Riposo Post-Notte
    if is_weekend and "no weekend" in v: return 999999
    if "solo notti" in v and tipo_turno != "N": return 999999
    if "solo mattina" in v and tipo_turno != "M": return 999999
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return 999999
    if tipo_turno == "M" and "no mattina" in v: return 999999
    if tipo_turno == "P" and "no pomeriggio" in v: return 999999

    # --- 2. LOGICA DI SATURAZIONE ARMONIZZATA ---
    # Calcoliamo la saturazione attuale
    saturazione = ore_tot_mese / target_mensile if target_mensile > 0 else 0
    
    # Se l'operatore ha già lavorato troppo rispetto agli altri, lo penalizziamo pesantemente
    punteggio = saturazione * 1000 

    # --- 3. SPINTA PER I "FERMI" ---
    # Se Neri o Cammarata sono sotto il 50% di saturazione, gli diamo priorità assoluta
    if saturazione < 0.5:
        punteggio -= 500

    return punteggio

if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna() & (edited_df['nome'] != "")].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # Per bilanciare meglio, assegniamo prima i turni a chi è più "scarico"
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

    # Analisi finale
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.dataframe(res_df)
    
    analisi = pd.DataFrame({
        "Target Mensile": op_validi.set_index('nome')['ore'] * 4,
        "Ore Effettive": res_df["ORE TOT"]
    })
    analisi["% Saturazione"] = (analisi["Ore Effettive"] / analisi["Target Mensile"] * 100).round(1)
    st.subheader("📊 Analisi Equità (Obiettivo: % simili per tutti)")
    st.table(analisi.sort_values("% Saturazione"))
