import streamlit as st
import pandas as pd
import calendar

# Configurazione della pagina
st.set_page_config(page_title="Gestione Turni Professionale", layout="wide")

st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# --- LISTA VINCOLI POSSIBILI ---
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
        {"nome": "Operatore Notte", "ore": 30, "vincoli": ["Solo Notti"]}
    ]

st.subheader("👥 Configurazione Personale e Vincoli")
st.write("Clicca sulla colonna **vincoli** per selezionare le opzioni dalla tendina.")

# --- TABELLA CON TENDINA (CONFIGURAZIONE) ---
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.ListColumn(
            "Vincoli",
            help="Seleziona i vincoli dal menu",
            width="large",
        ),
        # Questa parte abilita la scelta multipla dalla lista predefinita
        "vincoli": st.column_config.SelectboxColumn(
            "Vincoli",
            help="Scegli il vincolo principale",
            options=VINCOLI_DISPONIBILI,
            required=False,
        ) if False else st.column_config.MultiselectColumn( # Usiamo Multiselect per più vincoli
            "Vincoli",
            options=VINCOLI_DISPONIBILI,
            max_selections=3
        )
    }
)

# --- FUNZIONE LOGICA VINCOLI ---
def puo_lavorare(riga_op, tipo_turno, is_weekend):
    v_raw = riga_op.get('vincoli', [])
    v = [str(item).lower().strip() for item in v_raw] if isinstance(v_raw, list) else []
    
    if is_weekend and "no weekend" in v: return False
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    if tipo_turno == "N":
        if "no notte" in v: return False
        return "fa notti" in v or "solo notti" in v
    
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    
    return True

# --- GENERATORE ---
if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[(df_clean['nome'].notna()) & (df_clean['nome'] != "") & (df_clean['ore'] > 0)].copy()
    
    if not op_validi.empty:
        nomi_op = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
        ore_fatte = {nome: 0 for nome in nomi_op}

        for g_idx, col in enumerate(giorni_cols):
            is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
            oggi_occupati = []

            # 1. NOTTE (1)
            cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_lavorare(r, "N", is_we)]
            scelto_n = None
            for d in cand_n:
                if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                    if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N": scelto_n = d
            
            if not scelto_n and cand_n:
                disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
                if disp_n:
                    disp_n.sort(key=lambda x: ore_fatte[x])
                    scelto_n = disp_n[0]
            if scelto_n:
                res_df.at[scelto_n, col] = "N"; ore_fatte[scelto_n] += 9; oggi_occupati.append(scelto_n)

            # 2. MATTINA (2)
            cand_m = [n for n in nomi_op if n not in oggi_occupati and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "M", is_we)]
            cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_m.sort(key=lambda x: ore_fatte[x])
            for s in cand_m[:2]:
                res_df.at[s, col] = "M"; ore_fatte[s] += 7; oggi_occupati.append(s)

            # 3. POMERIGGIO (2)
            cand_p = [n for n in nomi_op if n not in oggi_occupati and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "P", is_we)]
            cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_p.sort(key=lambda x: ore_fatte[x])
            for s in cand_p[:2]:
                res_df.at[s, col] =
