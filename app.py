import streamlit as st
import pandas as pd
import calendar

st.set_page_config(page_title="Gestione Turni Avanzata", layout="wide")

st.title("🗓️ Generatore Turni Professionale")

# --- DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
        {"nome": "Operatore Notte", "ore": 30, "vincoli": ["Solo Notti", "No Weekend"]}
    ]

st.subheader("👥 Configura Operatori e Vincoli")
st.info("I vincoli validi sono: 'No Weekend', 'Solo Notti', 'Solo Mattina', 'Solo Pomeriggio', 'Fa Notti', 'No Pomeriggio'")
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

# --- FUNZIONE LOGICA VINCOLI MIGLIORATA ---
def puo_fare(riga_op, tipo_turno, is_weekend):
    # Prendi i vincoli e trasformali tutti in minuscolo per non sbagliare
    v_raw = riga_op.get('vincoli', [])
    if isinstance(v_raw, list):
        v = [str(item).lower().strip() for item in v_raw]
    else:
        v = []
    
    # 1. CONTROLLO WEEKEND (Il più importante)
    if is_weekend:
        if "no weekend" in v:
            return False
    
    # 2. CONTROLLO ESCLUSIVITÀ ("Solo")
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    # 3. CONTROLLO DIVIETI ("No")
    if tipo_turno == "N" and "no notte" in v: return False
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    
    # 4. ABILITAZIONE NOTTE (Chi non ha "Fa Notti" o "Solo Notti" non fa la notte)
    if tipo_turno == "N":
        return ("fa notti" in v or "solo notti" in v)

    return True

if st.button("🚀 GENERA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # Filtro operatori reali
    op_validi = edited_df[(edited_df['nome'].notna()) & (edited_df['ore'] > 0)].copy()
    nomi_op = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
    ore_fatte = {nome: 0 for nome in nomi_op}

    for g_idx, col in enumerate(giorni_cols):
        is_we = ("Sat" in col or "Sun" in col)
        oggi = []

        # --- NOTTE (1 persona) ---
        cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_fare(r, "N", is_we)]
        scelto_n = None
        
        # Priorità smonto/blocchi
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols
