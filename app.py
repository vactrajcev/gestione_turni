import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni Intelligence", layout="wide")
st.title("🗓️ Generatore Turni con Copertura Forzata")

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

st.subheader("👥 1. Configurazione Operatori")
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Notti", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"]),
        "ore": st.column_config.NumberColumn("Ore Settimanali")
    },
    key="editor_v4"
)

def valutazione_operatore(riga_op, tipo_turno, is_weekend, ore_sett_attuali, durata_turno, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    
    # Vincoli Blooccanti (Questi non si possono violare)
    if is_weekend and "no weekend" in v: return -1 # Impossibile
    if "solo notti" in v and tipo_turno != "N": return -1
    if "solo mattina" in v and tipo_turno != "M": return -1
    if "solo pomeriggio" in v and tipo_turno != "P": return -1
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return -1
    if tipo_turno == "M" and "no mattina" in v: return -1
    if tipo_turno == "P" and "no pomeriggio" in v: return -1
    
    # Protezione Smonto Notte (Bloccante)
    if g_idx > 0 and res_df.at[riga_op['nome'], giorni_cols[g_idx-1]] == "N": return -1

    # Calcolo punteggio idoneità (Più basso è, meglio è)
    punteggio = ore_sett_attuali
    # Penalità pesante se supera le ore, ma non bloccante se l'alternativa è il buco
    if ore_sett_attuali + durata_turno > riga_op.get('ore', 0):
        punteggio += 1000 
    
    return punteggio

if st.button("🚀 GENERA E FORZA COPERTURA 2-2-1"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna() & (edited_df['nome'] != "")].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}
    ore_sett_curr = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        wd = calendar.weekday(anno, mese, g_idx + 1)
        if wd == 0: ore_sett_curr = {n: 0 for n in op_validi['nome']}
        is_we = wd >= 5
        oggi = []

        for turno, ore_t, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            candidati = []
            for _, op in op_validi.iterrows():
                if op['nome'] not in oggi:
                    score = valutazione_operatore(op, turno, is_we, ore_sett_curr[op['nome']], ore_t, g_idx, res_df, giorni_cols)
                    if score != -1:
                        candidati.append((op['nome'], score))
            
            # Ordina per chi ha meno ore (o chi non ha ancora sforato)
            candidati.sort(key=lambda x: x[1])
            
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_sett_curr[s] += ore_t
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    # Visualizzazione
    st.dataframe(res_df)
    
    # Tabella Controllo
    conteggi = []
    for col in giorni_cols:
        c = res_df[col].tolist()
        conteggi.append({"Giorno": col, "M": c.count("M"), "P": c.count("P"), "N": c.count("N")})
    st.write("### 📊 Verifica Copertura (Target 2-2-1)")
    st.table(pd.DataFrame(conteggi).set_index("Giorno").T)
