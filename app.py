import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V10", layout="wide")
st.title("🗓️ Generatore Turni: Blocco 2 Notti + Turno Precedente")

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
    key="editor_v10"
)

def calcola_punteggio_equo(op, tipo_turno, is_weekend, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in op.get('vincoli', [])]
    nome = op['nome']
    target_mensile = op.get('ore', 0) * 4
    
    # --- REGOLE RIGIDE NOTTE ---
    if g_idx > 0:
        ieri = res_df.at[nome, giorni_cols[g_idx-1]]
        # 1. Se ieri ha fatto la PRIMA notte, OGGI DEVE FARE LA SECONDA (Regola 2 di fila)
        if ieri == "N":
            if g_idx > 1 and res_df.at[nome, giorni_cols[g_idx-2]] == "N":
                return 999999 # Già fatte 2, oggi SMONTO
            return 0 if tipo_turno == "N" else 999999 # Forza la seconda notte
        
        # 2. Se ieri era SMONTO (dopo 2 notti), oggi è RIPOSO
        if g_idx > 1 and res_df.at[nome, giorni_cols[g_idx-2]] == "N" and ieri == "-":
             return 999999 

    # --- REGOLA: PRIMA DELLA NOTTE DEVE AVER FATTO UN TURNO ---
    if tipo_turno == "N":
        if g_idx == 0: return 999999 # Non può iniziare il mese con una notte senza turno prima
        ieri = res_df.at[nome, giorni_cols[g_idx-1]]
        if ieri == "-": return 999999 # Non può fare notte se ieri era a riposo

    # --- VINCOLI STANDARD ---
    if is_weekend and "no weekend" in v: return 999999
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return 999999
    if "solo mattina" in v and tipo_turno != "M": return 999999
    if "no pomeriggio" in v and tipo_turno == "P": return 999999

    # --- BILANCIAMENTO ORE ---
    saturazione = ore_tot_mese / target_mensile if target_mensile > 0 else 0
    punteggio = saturazione * 1000
    
    # Spinta per chi è molto sotto target (come Neri o Ristova nei feriali)
    if saturazione < 0.7: punteggio -= 500
    
    return punteggio

if st.button("🚀 GENERA CON REGOLA 2 NOTTI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna()].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # Priorità alla Notte per gestire la sequenza forzata
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

    # Visualizzazione
    st.subheader("📅 Tabella Turni (Sequenza: Giorno -> N -> N -> Smonto)")
    st.dataframe(res_df)
    
    # Verifica Copertura 2-2-1
    st.subheader("✅ Verifica Copertura 2-2-1")
    conteggi = {c: {"M": res_df[c].tolist().count("M"), "P": res_df[c].tolist().count("P"), "N": res_df[c].tolist().count("N")} for c in giorni_cols}
    st.table(pd.DataFrame(conteggi))

    # Analisi Ore
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.subheader("📊 Analisi Equità Ore")
    analisi = pd.DataFrame({
        "Target": op_validi.set_index('nome')['ore'] * 4,
        "Effettive": res_df["ORE TOT"]
    })
    analisi["% Sat."] = (analisi["Effettive"] / analisi["Target"] * 100).round(1)
    st.table(analisi.sort_values("% Sat."))
