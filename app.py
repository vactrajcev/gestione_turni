import streamlit as st
import pandas as pd
import calendar

# 1. Configurazione Pagina
st.set_page_config(page_title="Gestione Turni Avanzata", layout="wide")

st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# 2. Lista Vincoli predefiniti
VINCOLI_LISTA = [
    "No Weekend", 
    "Solo Notti", 
    "Solo Mattina", 
    "Solo Pomeriggio", 
    "Fa Notti", 
    "No Mattina", 
    "No Pomeriggio", 
    "No Notte"
]

# 3. Inizializzazione Dati
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
        {"nome": "Operatore 1", "ore": 30, "vincoli": ["Solo Notti", "No Weekend"]}
    ]

st.subheader("👥 Configurazione Personale e Vincoli")
st.info("💡 Clicca nella colonna 'vincoli' per selezionare le opzioni dalla tendina.")

# 4. Tabella con Tendina Multiselect (Correzione Errore Riga 43)
# Usiamo una configurazione più semplice per evitare il TypeError visto in image_580266.png
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli",
            options=VINCOLI_LISTA,
            width="medium"
        ),
        "ore": st.column_config.NumberColumn("Ore", min_value=0, max_value=50)
    },
    key="editor_turni"
)

# 5. Funzione Logica Vincoli
def puo_lavorare(riga_op, tipo_turno, is_weekend):
    v_raw = riga_op.get('vincoli', [])
    v = [str(item).lower().strip() for item in v_raw] if isinstance(v_raw, list) else []
    
    if is_weekend and "no weekend" in v: return False
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    if tipo_turno == "N":
        return "fa notti" in v or "solo notti" in v
    
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    return True

# 6. Generazione Turni
if st.button("🚀 GENERA TABELLA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # Pulizia Dati (Correzione AttributeError riga 55)
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[(df_clean['nome'].notna()) & (df_clean['nome'] != "") & (df_clean['ore'] > 0)].copy()
    
    if op_validi.empty:
        st.error("Inserisci operatori validi!")
    else:
        nomi_op = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
        ore_fatte = {nome: 0 for nome in nomi_op}

        for g_idx, col in enumerate(giorni_cols):
            # Calcolo weekend: Sabato=5, Domenica=6
            wd_idx = calendar.weekday(anno, mese, g_idx + 1)
            is_we = wd_idx >= 5
            oggi = []

            # --- NOTTE (1) ---
            cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_lavorare(r, "N", is_we)]
            scelto_n = None
            for d in cand_n:
                if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                    if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N": scelto_n = d
            
            if not scelto_n and cand_n:
                disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
                if disp_n:
                    disp_n.sort(key=lambda x: ore_fatte[x])
                    scelto
