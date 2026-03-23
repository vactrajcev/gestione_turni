import streamlit as st
import pandas as pd
import calendar

st.set_page_config(page_title="Gestione Turni Bilanciata", layout="wide")

st.title("🗓️ Generatore Turni Professionale")

# --- DATABASE OPERATORI INIZIALE ---
default_ops = [
    {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
    {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
    {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
    {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
    {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
    {"nome": "BERTOLETTI B. (30)", "ore": 30, "vincoli": []},
    {"nome": "PALMIERI J. (28)", "ore": 25, "vincoli": []},
    {"nome": "MOSTACCHI M. (25)", "ore": 25, "vincoli": []}
]

if 'operatori' not in st.session_state:
    st.session_state.operatori = default_ops

# Pulsante per resettare i dati
if st.sidebar.button("Reset Tabella Operatori"):
    st.session_state.operatori = default_ops
    st.rerun()

st.subheader("👥 Lista Operatori (Modifica nomi e ore qui)")
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

def ha_vincolo(riga_op, testo_vincolo):
    v = riga_op.get('vincoli', [])
    return testo_vincolo in v if isinstance(v, list) else False

if st.button("🚀 GENERA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # --- FILTRO OPERATORI REALI ---
    op_validi_df = edited_df[
        (edited_df['nome'].notna
