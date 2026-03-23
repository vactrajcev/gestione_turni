import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestione Turni - Versione Finale", layout="wide")
st.title("🗓️ Generatore Turni Professionale")

# --- DATI INIZIALI ---
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

# --- INTERFACCIA ---
st.subheader("👥 Configurazione Operatori")
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli", 
            options=["No Weekend", "Solo Notti", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"]
        ),
        "ore": st.column_config.NumberColumn("Ore Settimanali", min_value=0)
    },
    key="editor_finale"
)

# --- FUNZIONI DI SUPPORTO ---
def puo_lavorare(riga_op, tipo_turno, is_weekend, ore_sett_attuali, durata_turno):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    if ore_sett_attuali + durata_turno > riga_op.get('ore', 0): return False
    if is_weekend and "no weekend" in v: return False
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    if tipo_turno == "N": return "fa notti" in v or "solo notti" in v
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    return True

def to_excel(df):
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=True, sheet_name='Turni')
        return output.getvalue()
    except ImportError:
        return None

# --- GENERAZIONE ---
if st.button("🚀 GENERA TABELLA TURNI"):
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

        for turno, ore_t in [("N", 9), ("M", 7), ("P", 8)]:
            posti = 1 if turno == "N" else 2
            validi = [n for n in op_validi['nome'] if n not in oggi and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], turno, is_we, ore_sett_curr[n], ore_t)]
            validi = [v for v in validi if g_idx == 0 or res_df.at[v, giorni_cols[g_idx-1]] != "N"]
            validi.sort(key=lambda x: ore_tot_mese[x])
            
            for s in validi[:posti]:
                res_df.at[s, col] = turno
                ore_sett_curr[s] += ore_t
                ore_tot_mese[s] += ore_t
                oggi.append(s)

    res_df["TOT ORE"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.dataframe(res_df)
    
    excel_data = to_excel(res_df)
    if excel_data:
        st.download_button("📥 Scarica Excel", data=excel_data, file_name="turni.xlsx", mime="application/vnd.ms-excel")
    else:
        st.error("Errore: libreria 'xlsxwriter' non installata nel sistema.")
