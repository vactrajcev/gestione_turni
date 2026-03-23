
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
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []}
    ]

st.subheader("👥 Configura Operatori e Vincoli")
st.info("💡 Vincoli riconosciuti: 'No Weekend', 'Solo Notti', 'Solo Mattina', 'Solo Pomeriggio', 'Fa Notti', 'No Pomeriggio'")
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

# --- FUNZIONE LOGICA VINCOLI ---
def puo_fare(riga_op, tipo_turno, is_weekend):
    v_raw = riga_op.get('vincoli', [])
    v = [str(item).lower().strip() for item in v_raw] if isinstance(v_raw, list) else []
    
    # 1. BLOCCO WEEKEND RIGIDO
    if is_weekend and "no weekend" in v:
        return False
    
    # 2. BLOCCHI "SOLO"
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    # 3. ABILITAZIONE NOTTE
    if tipo_turno == "N":
        if "no notte" in v: return False
        return "fa notti" in v or "solo notti" in v
    
    # 4. ALTRI DIVIETI
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    
    return True

if st.button("🚀 GENERA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    
    # Creazione colonne giorni
    giorni_cols = []
    for g in range(1, num_giorni + 1):
        wd = calendar.weekday(anno, mese, g)
        giorni_cols.append(f"{g}-{calendar.day_name[wd][:3]}")
    
    # --- CORREZIONE ERRORE RIGA 55 ---
    # Convertiamo la colonna ore in numeri in modo sicuro
    df_pulito = edited_df.copy()
    df_pulito['ore'] = pd.to_numeric(df_pulito['ore'], errors='coerce').fillna(0)
    
    op_validi = df_pulito[
        (df_pulito['nome'].notna()) & 
        (df_pulito['nome'] != "") & 
        (df_pulito['nome'].str.lower() != "none") &
        (df_pulito['ore'] > 0)
    ].copy()
    
    nomi_op = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
    ore_fatte = {nome: 0 for nome in nomi_op}

    for g_idx, col in enumerate(
