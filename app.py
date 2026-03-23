import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni - Ottimizzazione Carico", layout="wide")
st.title("🗓️ Generatore Turni con Priorità Recupero Ore")

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

edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="editor_ottimizzato")

def valutazione_avanzata(op, tipo_turno, is_weekend, ore_sett_attuali, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in op.get('vincoli', [])] if isinstance(op.get('vincoli'), list) else []
    nome = op['nome']
    target_sett = op.get('ore', 0)
    
    # Vincoli Bloccanti Rigidi
    if is_weekend and "no weekend" in v: return -1
    if "solo notti" in v and tipo_turno != "N": return -1
    if "solo mattina" in v and tipo_turno != "M": return -1
    if "solo pomeriggio" in v and tipo_turno != "P": return -1
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return -1
    if tipo_turno == "M" and "no mattina" in v: return -1
    if tipo_turno == "P" and "no pomeriggio" in v: return -1
    if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": return -1

    # CALCOLO PUNTEGGIO INTELLIGENTE
    # Più il punteggio è BASSO, più l'operatore ha probabilità di essere scelto
    punteggio = ore_tot_mese 

    # 1. Se è un giorno feriale (Lun-Ven) e l'operatore NON può lavorare nel weekend,
    # gli diamo una priorità altissima per farlo lavorare ora.
    if not is_weekend and "no weekend" in v:
        punteggio -= 50 # Bonus priorità feriale

    # 2. Se l'operatore è molto indietro con le ore rispetto al suo target settimanale
    if ore_sett_attuali < (target_sett - 8):
        punteggio -= 30 # Bonus recupero ore

    # 3. Penalità se supera il limite settimanale (ma meno rigida per permettere copertura)
    if ore_sett_attuali + 8 > target_sett:
        punteggio += 100

    return punteggio

if st.button("🚀 GENERA TURNI OTTIMIZZATI"):
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
                    score = valutazione_avanzata(op, turno, is_we, ore_sett_curr[op['nome']], ore_tot_mese[op['nome']], g_idx, res_df, giorni_cols)
                    if score != -1:
                        candidati.append((op['nome'], score))
            
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_sett_curr[s] += ore_t
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    st.subheader("📅 Tabella Turni (Ristova e Neri prioritarie in settimana)")
    st.dataframe(res_df)
    
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.subheader("📊 Analisi Carico Bilanciato")
    analisi = pd.DataFrame({
        "Target Sett.": op_validi.set_index('nome')['ore'],
        "Ore Effettive": res_df["ORE TOT"],
        "Target Mese (x4)": op_validi.set_index('nome')['ore'] * 4
    })
    st.table(analisi)
