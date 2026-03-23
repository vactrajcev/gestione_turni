import streamlit as st
import pandas as pd
import calendar

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni Avanzata", layout="wide")
st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# Lista Vincoli per la Tendina
VINCOLI_LISTA = ["No Weekend", "Solo Notti", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"]

# Inizializzazione Dati
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []}
    ]

st.subheader("👥 Configurazione Personale e Vincoli")
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=VINCOLI_LISTA),
        "ore": st.column_config.NumberColumn("Ore", min_value=0)
    }
)

def puo_lavorare(riga_op, tipo_turno, is_weekend):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    if is_weekend and "no weekend" in v: return False
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    if tipo_turno == "N": return "fa notti" in v or "solo notti" in v
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    return True

if st.button("🚀 GENERA TABELLA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[(df_clean['nome'].notna()) & (df_clean['nome'] != "") & (df_clean['ore'] > 0)].copy()
    
    if op_validi.empty:
        st.error("Inserisci operatori con ore valide!")
    else:
        nomi_op = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
        ore_fatte = {n: 0 for n in nomi_op}

        for g_idx, col in enumerate(giorni_cols):
            is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
            oggi = []

            # 1. NOTTE (1)
            cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_lavorare(r, "N", is_we)]
            scelto_n = None
            # Priorità a chi deve finire il raddoppio
            for d in cand_n:
                if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                    if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N": scelto_n = d
            
            if not scelto_n and cand_n:
                disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
                if disp_n:
                    disp_n.sort(key=lambda x: ore_fatte[x])
                    scelto_n = disp_n[0]
            
            if scelto_n:
                res_df.at[scelto_n, col] = "N"; ore_fatte[scelto_n] += 9; oggi.append(scelto_n)

            # 2. MATTINA (2)
            cand_m = [n for n in nomi_op if n not in oggi and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "M", is_we)]
            cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_m.sort(key=lambda x: ore_fatte[x])
            for s in cand_m[:2]:
                res_df.at[s, col] = "M"; ore_fatte[s] += 7; oggi.append(s)

            # 3. POMERIGGIO (2)
            cand_p = [n for n in nomi_op if n not in oggi and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "P", is_we)]
            cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_p.sort(key=lambda x: ore_fatte[x])
            for s in cand_p[:2]:
                res_df.at[s, col] = "P"; ore_fatte[s] += 8

        res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
        st.dataframe(res_df)
        csv = res_df.to_csv().encode('utf-8')
        st.download_button("📥 Scarica Turni", csv, "turni.csv", "text/csv")
