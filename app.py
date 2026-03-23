import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni Equa", layout="wide")
st.title("🗓️ Generatore Turni con Bilanciamento Proporzionale")

# --- DATABASE OPERATORI ---
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

edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

def calcola_punteggio_equo(op, tipo_turno, is_weekend, ore_sett_curr, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in op.get('vincoli', [])]
    nome = op['nome']
    target_mese = op.get('ore', 0) * 4 # Target indicativo mensile
    
    # 1. VINCOLI RIGIDI (Impossibile assegnare)
    if is_weekend and "no weekend" in v: return 999999
    if "solo notti" in v and tipo_turno != "N": return 999999
    if "solo mattina" in v and tipo_turno != "M": return 999999
    if "solo pomeriggio" in v and tipo_turno != "P": return 999999
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return 999999
    if tipo_turno == "M" and "no mattina" in v: return 999999
    if tipo_turno == "P" and "no pomeriggio" in v: return 999999
    if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": return 999999

    # 2. LOGICA PROPORZIONALE (Il cuore del bilanciamento)
    # Calcoliamo quanto l'operatore è "pieno" rispetto al suo contratto (da 0.0 a 1.0 e oltre)
    percentuale_carico = ore_tot_mese / target_mese if target_mese > 0 else 0
    
    # Preferenza a chi ha la percentuale più bassa
    punteggio = percentuale_carico * 100 

    # 3. SPINTA PER CHI HA VINCOLI (Neri e Ristova)
    # Se è feriale e hanno vincoli weekend, "costringiamoli" a lavorare ora per liberare gli altri
    if not is_weekend and "no weekend" in v:
        punteggio -= 20 

    return punteggio

if st.button("🚀 GENERA TURNI PROPORZIONALI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna() & (edited_df['nome'] != "")].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # Target 2-2-1
        for turno, ore_t, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            candidati = []
            for _, op in op_validi.iterrows():
                if op['nome'] not in oggi:
                    score = calcola_punteggio_equo(op, turno, is_we, 0, ore_tot_mese[op['nome']], g_idx, res_df, giorni_cols)
                    if score < 900000:
                        candidati.append((op['nome'], score))
            
            # Scegliamo i candidati con la percentuale di carico più bassa
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    # Visualizzazione
    res_df["ORE TOTALI"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.subheader("📅 Tabella Turni Bilanciata")
    st.dataframe(res_df)
    
    st.subheader("📊 Analisi Equità (Sforamento Proporzionale)")
    analisi = pd.DataFrame({
        "Target Mensile": op_validi.set_index('nome')['ore'] * 4,
        "Ore Effettive": res_df["ORE TOTALI"]
    })
    analisi["% Saturazione"] = (analisi["Ore Effettive"] / analisi["Target Mensile"] * 100).round(1).astype(str) + "%"
    st.table(analisi)
