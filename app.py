import streamlit as st
import pandas as pd
import calendar

st.set_page_config(page_title="Gestione Turni Avanzata", layout="wide")

st.title("🗓️ Generatore Turni con Vincoli Intelligenti")

# --- CONFIGURAZIONE INIZIALE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "NUOVO NOTTURNO", "ore": 38, "vincoli": ["Solo Notti"]}
    ]

# Sidebar per il reset
if st.sidebar.button("Reset Tabella"):
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "NUOVO NOTTURNO", "ore": 38, "vincoli": ["Solo Notti"]}
    ]
    st.rerun()

st.subheader("👥 Configura Operatori e Vincoli")
# Possibilità di scegliere tra vincoli predefiniti
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

# --- FUNZIONE LOGICA VINCOLI ---
def puo_fare_turno(riga_op, tipo_turno, is_weekend):
    v = riga_op.get('vincoli', [])
    if not isinstance(v, list): v = []
    
    # Vincolo Weekend
    if is_weekend and "No Weekend" in v:
        return False
    
    # Logica specifica per tipo di turno
    if tipo_turno == "N":
        if "Solo Mattina" in v or "Solo Pomeriggio" in v or "No Notte" in v: return False
        return "Fa Notti" in v or "Solo Notti" in v
        
    if tipo_turno == "M":
        if "Solo Notti" in v or "Solo Pomeriggio" in v or "No Mattina" in v: return False
        return True # Se non ha blocchi, può fare mattina
        
    if tipo_turno == "P":
        if "Solo Notti" in v or "Solo Mattina" in v or "No Pomeriggio" in v: return False
        return True
    
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

        # 1. NOTTE (Priorità a chi DEVE fare solo notti o chi ha il blocco da 2)
        cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_fare_turno(r, "N", is_we)]
        scelto_n = None
        
        # Controllo smonto e blocchi
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        
        if not scelto_n and cand_n:
            disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            disp_n.sort(key=lambda x: ore_fatte[x])
            if disp_n: scelto_n = disp_n[0]
            
        if scelto_n:
            res_df.at[scelto_n, col] = "N"
            ore_fatte[scelto_n] += 9
            oggi.append(scelto_n)

        # 2. MATTINA (2 persone)
        cand_m = [r['nome'] for _, r in op_validi.iterrows() if r['nome'] not in oggi and puo_fare_turno(r, "M", is_we)]
        # Filtro smonto notte
        cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
        cand_m.sort(key=lambda x: ore_fatte[x])
        
        for s in cand_m[:2]:
            res_df.at[s, col] = "M"
            ore_fatte[s] += 7
            oggi.append(s)

        # 3. POMERIGGIO (2 persone)
        cand_p = [r['nome'] for _, r in op_validi.iterrows() if r['nome'] not in oggi and puo_fare_turno(r, "P", is_we)]
        cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
        cand_p.sort(key=lambda x: ore_fatte[x])
        
        for s in cand_p[:2]:
            res_df.at[s, col] = "P"
            ore_fatte[s] += 8

    res_df["TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.dataframe(res_df)
    
    # Verifica 2-2-1
    check = pd.DataFrame({
        "M": [res_df[c].tolist().count("M") for c in giorni_cols],
        "P": [res_df[c].tolist().count("P") for c in giorni_cols],
        "N": [res_df[c].tolist().count("N") for c in giorni_cols]
    }, index=giorni_cols).T
    st.write("### Verifica Copertura")
    st.table(check)
