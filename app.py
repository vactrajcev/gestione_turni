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

# Pulsante per resettare i dati nella sidebar
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
    
    # --- FILTRO OPERATORI REALI (CORRETTO) ---
    op_validi_df = edited_df[
        (edited_df['nome'].notna()) & 
        (edited_df['nome'].str.lower() != "none") & 
        (edited_df['nome'] != "") & 
        (edited_df['ore'] > 0)
    ].copy()
    
    nomi_op = op_validi_df['nome'].tolist()
    
    # Creiamo la tabella solo con i nomi reali presenti nell'elenco
    res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
    ore_fatte = {nome: 0 for nome in nomi_op}

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi = []

        # 1. NOTTE (1 PERSONA)
        cand_n = [r['nome'] for _, r in op_validi_df.iterrows() if ha_vincolo(r, "Fa Notti")]
        scelto_n = None
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        
        if not scelto_n and cand_n:
            disp_n = [d for d in cand_n if (g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N")]
            disp_n.sort(key=lambda x: ore_fatte[x])
            if disp_n: scelto_n = disp_n[0]
        
        if scelto_n:
            res_df.at[scelto_n, col] = "N"
            ore_fatte[scelto_n] += 9
            oggi.append(scelto_n)

        # 2. MATTINA (2 PERSONE)
        cand_m = []
        for _, r in op_validi_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_m.append(n)
        
        cand_m.sort(key=lambda x: ore_fatte[x])
        for s in cand_m[:2]:
            res_df.at[s, col] = "M"
            ore_fatte[s] += 7
            oggi.append(s)

        # 3. POMERIGGIO (2 PERSONE)
        cand_p = []
        for _, r in op_validi_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if ha_vincolo(r, "No Pomeriggio") or ha_vincolo(r, "Solo Mattina"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_p.append(n)
        
        cand_p.sort(key=lambda x: ore_fatte[x])
        for s in cand_p[:2]:
            res_df.at[s, col] = "P"
            ore_fatte[s] += 8

    # Colonna ORE TOTALE
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    
    st.write("### 📅 Tabella Turni")
    st.dataframe(res_df)

    # Verifica Copertura Giornaliera
    st.write("### ✅ Verifica Copertura (2-2-1)")
    check = pd.DataFrame({
        "M": [res_df[c].tolist().count("M") for c in giorni_cols],
        "P": [res_df[c].tolist().count("P") for c in giorni_cols],
        "N": [res_df[c].tolist().count("N") for c in giorni_cols]
    }, index=giorni_cols).T
    st.table(check)

    st.download_button("📥 Scarica Excel", res_df.to_csv().encode('utf-8'), "turni_aprile.csv")
