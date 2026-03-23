import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni Bilanciata", layout="wide")
st.title("🗓️ Generatore Turni con Bilanciamento Carico")

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
    key="editor_bilanciato"
)

def valutazione_bilanciata(riga_op, tipo_turno, is_weekend, ore_sett_attuali, durata_turno, ore_tot_mese, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    nome = riga_op['nome']
    
    # Vincoli Bloccanti
    if is_weekend and "no weekend" in v: return -1
    if "solo notti" in v and tipo_turno != "N": return -1
    if "solo mattina" in v and tipo_turno != "M": return -1
    if "solo pomeriggio" in v and tipo_turno != "P": return -1
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return -1
    if tipo_turno == "M" and "no mattina" in v: return -1
    if tipo_turno == "P" and "no pomeriggio" in v: return -1
    if g_idx > 0 and res_df.at[nome, giorni_cols[g_idx-1]] == "N": return -1

    # LOGICA DI BILANCIAMENTO
    limite_sett = riga_op.get('ore', 0)
    
    # Punteggio base = ore già fatte nel mese (per distribuire il carico)
    # Sommiamo le ore settimanali attuali per rispettare il contratto a breve termine
    punteggio = ore_tot_mese + (ore_sett_attuali * 2) 
    
    # Penalità enorme se supera il limite settimanale
    if ore_sett_attuali + durata_turno > limite_sett:
        punteggio += 5000 
    
    return punteggio

if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna() & (edited_df['nome'] != "")].copy()
    nomi = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_tot_mese = {n: 0 for n in nomi}
    ore_sett_curr = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        wd = calendar.weekday(anno, mese, g_idx + 1)
        if wd == 0: ore_sett_curr = {n: 0 for n in nomi} # Reset Lunedì
        is_we = wd >= 5
        oggi = []

        # Distribuzione turni
        for turno, ore_t, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            candidati = []
            for _, op in op_validi.iterrows():
                if op['nome'] not in oggi:
                    score = valutazione_bilanciata(op, turno, is_we, ore_sett_curr[op['nome']], ore_t, ore_tot_mese[op['nome']], g_idx, res_df, giorni_cols)
                    if score != -1:
                        candidati.append((op['nome'], score))
            
            # Scegliamo chi ha il punteggio più basso (meno carico)
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_sett_curr[s] += ore_t
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    # Output Risultati
    res_df["ORE TOTALI"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.subheader("📅 Tabella Turni Bilanciata")
    st.dataframe(res_df)
    
    st.subheader("📊 Analisi Carico di Lavoro")
    analisi = pd.DataFrame({
        "Ore Contrattuali Sett.": op_validi.set_index('nome')['ore'],
        "Ore Effettive Mese": res_df["ORE TOTALI"],
        "Target Mensile (x4)": op_validi.set_index('nome')['ore'] * 4
    })
    st.table(analisi)
