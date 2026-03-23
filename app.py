import streamlit as st
import pandas as pd
import calendar

# Configurazione della pagina
st.set_page_config(page_title="Gestione Turni Professionale", layout="wide")

st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# --- LISTA VINCOLI POSSIBILI (Per la tendina) ---
VINCOLI_DISPONIBILI = [
    "No Weekend", 
    "Solo Notti", 
    "Solo Mattina", 
    "Solo Pomeriggio", 
    "Fa Notti", 
    "No Mattina", 
    "No Pomeriggio", 
    "No Notte"
]

# --- DATABASE OPERATORI INIZIALE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore": 25, "vincoli": []}
    ]

st.subheader("👥 Configurazione Personale e Vincoli")
st.info("💡 Clicca nella colonna 'Vincoli' per aggiungere opzioni dalla tendina.")

# --- TABELLA INTERATTIVA CON TENDINA ---
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli",
            options=VINCOLI_DISPONIBILI,
            max_selections=5,
            help="Seleziona i vincoli per questo operatore"
        ),
        "ore": st.column_config.NumberColumn(
            "Ore Contrattuali",
            min_value=0,
            max_value=50,
            step=1
        )
    }
)

# --- FUNZIONE LOGICA VINCOLI ---
def puo_lavorare(riga_op, tipo_turno, is_weekend):
    v_raw = riga_op.get('vincoli', [])
    v = [str(item).lower().strip() for item in v_raw] if isinstance(v_raw, list) else []
    
    # 1. Blocco Weekend Rigido
    if is_weekend and "no weekend" in v:
        return False
    
    # 2. Controllo Esclusività ("Solo")
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    # 3. Controllo Turno Notte
    if tipo_turno == "N":
        if "no notte" in v: return False
        return "fa notti" in v or "solo notti" in v
    
    # 4. Controllo Divieti Generici
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    
    return True

# --- GENERATORE ---
if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # Pulizia dati (Correzione AttributeError riga 55)
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df
