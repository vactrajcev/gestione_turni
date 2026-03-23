import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni Intelligence", layout="wide")
st.title("🗓️ Generatore Turni con Riepilogo Ore")

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
    key="editor_v5"
)

def valutazione_operatore(riga_op, tipo_turno, is_weekend, ore_sett_attuali, durata_turno, g_idx, res_df, giorni_cols):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    
    if is_weekend and "no weekend" in v: return -1
    if "solo notti" in v and tipo_turno != "N": return -1
    if "solo mattina" in v and tipo_turno != "M": return -1
    if "solo pomeriggio" in v and tipo_turno != "P": return -1
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return -1
    if tipo_turno == "M" and "no mattina" in v: return -1
    if tipo_turno == "P" and "no pomeriggio" in v: return -1
    if g_idx > 0 and res_df.at[riga_op['nome'], giorni_cols[g_idx-1]] == "N": return -1

    punteggio = ore_sett_attuali
    if ore_sett_attuali + durata_turno > riga_op.get('ore', 0):
        punteggio += 1000 
    
    return punteggio

def to_excel(df):
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=True, sheet_name='Turni')
        return output.getvalue()
    except:
        return None

if st.button("🚀 GENERA E MOSTRA ORE TOTALI"):
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
            
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_sett_curr[s] += ore_t
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    # --- AGGIUNTA COLONNA ORE TOTALI ---
    res_df["ORE TOTALI"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    
    st.subheader("📅 2. Tabella Turni con Riepilogo Ore")
    st.dataframe(res_df)
    
    # --- TABELLA DI CONFRONTO ORE ---
    st.subheader("📊 3. Analisi Ore: Contratto vs Effettive")
    analisi_ore = pd.DataFrame({
        "Contratto Settimanale": op_validi.set_index('nome')['ore'],
        "Ore Totali Mese (Effettive)": res_df["ORE TOTALI"]
    })
    # Calcolo indicativo ore mensili medie (Settimanale * 4)
    analisi_ore["Target Mensile (circa)"] = analisi_ore["Contratto Settimanale"] * 4
    st.table(analisi_ore)

    # --- VERIFICA COPERTURA ---
    st.subheader("✅ 4. Verifica Copertura Giornaliera (2-2-1)")
    conteggi = []
    for col in giorni_cols:
        c = res_df[col].tolist()
        conteggi.append({"Giorno": col, "M": c.count("M"), "P": c.count("P"), "N": c.count("N")})
    st.table(pd.DataFrame(conteggi).set_index("Giorno").T)

    # Export
    excel_data = to_excel(res_df)
    if excel_data:
        st.download_button("📥 Scarica Excel", data=excel_data, file_name="turni_con_riepilogo.xlsx")
