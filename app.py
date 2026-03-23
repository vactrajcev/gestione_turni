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
        {"nome": "Operatore 1", "ore": 30, "vincoli": ["Solo Notti", "No Weekend"]}
    ]

st.subheader("👥 Configura Operatori e Vincoli")
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

# --- LOGICA VINCOLI BLINDATA ---
def puo_fare(riga_op, tipo_turno, is_weekend):
    v = riga_op.get('vincoli', [])
    if not isinstance(v, list): v = []
    
    # 1. Controllo Weekend
    if is_weekend and "No Weekend" in v:
        return False
    
    # 2. Controllo ESCLUSIVITÀ (I "Solo")
    if "Solo Notti" in v and tipo_turno != "N": return False
    if "Solo Mattina" in v and tipo_turno != "M": return False
    if "Solo Pomeriggio" in v and tipo_turno != "P": return False
    
    # 3. Controllo DIVIETI (I "No")
    if tipo_turno == "N" and "No Notte" in v: return False
    if tipo_turno == "M" and "No Mattina" in v: return False
    if tipo_turno == "P" and "No Pomeriggio" in v: return False
    
    # 4. Abilitazione Notte
    if tipo_turno == "N":
        return "Fa Notti" in v or "Solo Notti" in v

    return True

if st.button("🚀 GENERA TURNI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[(edited_df['nome'].notna()) & (edited_df['ore'] > 0)].copy()
    nomi_op = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
    ore_fatte = {nome: 0 for nome in nomi_op}

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi = []

        # --- NOTTE (1 persona) ---
        cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_fare(r, "N", is_we)]
        scelto_n = None
        # Priorità a chi deve finire il blocco di 2
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        
        if not scelto_n and cand_n:
            disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            disp_n.sort(key=lambda x: ore_fatte[x])
            if disp_n: scelto_n = disp_n[0]
        
        if scelto_n:
            res_df.at[scelto_n, col] = "N"; ore_fatte[scelto_n] += 9; oggi.append(scelto_n)

        # --- MATTINA (2 persone) ---
        cand_m = [r['nome'] for _, r in op_validi.iterrows() if r['nome'] not in oggi and puo_fare(r, "M", is_we)]
        cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"] # No smonto
        cand_m.sort(key=lambda x: ore_fatte[x])
        for s in cand_m[:2]:
            res_df.at[s, col] = "M"; ore_fatte[s] += 7; oggi.append(s)

        # --- POMERIGGIO (2 persone) ---
        cand_p = [r['nome'] for _, r in op_validi.iterrows() if r['nome'] not in oggi and puo_fare(r, "P", is_we)]
        cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
        cand_p.sort(key=lambda x: ore_fatte[x])
        for s in cand_p[:2]:
            res_df.at[s, col] = "P"; ore_fatte[s] += 8

    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.dataframe(res_df)
    
    # Tabella di controllo 2-2-1
    check = pd.DataFrame({
        "M": [res_df[c].tolist().count("M") for c in giorni_cols],
        "P": [res_df[c].tolist().count("P") for c in giorni_cols],
        "N": [res_df[c].tolist().count("N") for c in giorni_cols]
    }, index=giorni_cols).T
    st.write("### Verifica Copertura (2-2-1)")
    st.table(check)
