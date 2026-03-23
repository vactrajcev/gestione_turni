
import streamlit as st
import pandas as pd
import calendar

st.set_page_config(page_title="Gestione Turni Bilanciata", layout="wide")

st.title("🗓️ Generatore Turni con Bilanciamento Ore")
st.markdown("Questo sistema assegna i turni a chi ha lavorato meno per rispettare il contratto settimanale.")

# --- DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore_sett": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore_sett": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore_sett": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore_sett": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore_sett": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore_sett": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore_sett": 28, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore_sett": 25, "vincoli": []}
    ]

edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

def ha_vincolo(riga_op, testo_vincolo):
    v = riga_op.get('vincoli', [])
    return testo_vincolo in v if isinstance(v, list) else False

if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    nomi_op = edited_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op + ["ESTERNI"], columns=giorni_cols)
    
    # Dizionario per tracciare le ore totali fatte da ognuno
    ore_fatte = {nome: 0 for nome in nomi_op}
    ore_fatte["ESTERNI"] = 0

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi = []

        # 1. NOTTE (1 PERSONA) - 9 ore
        cand_n = [r['nome'] for _, r in edited_df.iterrows() if ha_vincolo(r, "Fa Notti")] + ["ESTERNI"]
        scelto_n = None
        # Priorità a chi deve finire il blocco di 2 notti
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        
        if not scelto_n:
            # Scegliamo tra chi può lavorare (no smonto) e ha meno ore totali
            disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            disp_n.sort(key=lambda x: ore_fatte[x]) # BILANCIAMENTO: prende chi ha lavorato meno
            scelto_n = disp_n[0] if disp_n else "ESTERNI"
        
        res_df.at[scelto_n, col] = "N"
        ore_fatte[scelto_n] += 9
        oggi.append(scelto_n)

        # 2. MATTINA (2 PERSONE) - 7 ore
        cand_m = []
        for _, r in edited_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_m.append(n)
        
        # Ordina i candidati per ore fatte (crescente)
        cand_m.sort(key=lambda x: ore_fatte[x])
        for s in cand_m[:2]:
            res_df.at[s, col] = "M"
            ore_fatte[s] += 7
            oggi.append(s)

        # 3. POMERIGGIO (2 PERSONE) - 8 ore
        cand_p = []
        for _, r in edited_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if ha_vincolo(r, "No Pomeriggio") or ha_vincolo(r, "Solo Mattina"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            cand_p.append(n)
        
        cand_p.sort(key=lambda x: ore_fatte[x])
        for s in cand_p[:2]:
            res_df.at[s, col] = "P"
            ore_fatte[s] += 8

    # Visualizzazione Risultati
    res_df["ORE TOTALI"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    st.dataframe(res_df)
    
    st.write("### Verifica Copertura Giornaliera (2-2-1)")
    check = pd.DataFrame({
        "M": [res_df[c].tolist().count("M") for c in giorni_cols],
        "P": [res_df[c].tolist().count("P") for c in giorni_cols],
        "N": [res_df[c].tolist().count("N") for c in giorni_cols]
    }, index=giorni_cols).T
    st.table(check)
