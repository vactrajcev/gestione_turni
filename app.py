import streamlit as st
import pandas as pd
import calendar

st.set_page_config(page_title="Gestione Turni Bilanciata", layout="wide")

st.title("🗓️ Generatore Turni con Filtri Avanzati")

# --- DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore_sett": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore_sett": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore_sett": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore_sett": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore_sett": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore_sett": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore_sett": 25, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore_sett": 25, "vincoli": []}
    ]

# Editor della tabella
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

def ha_vincolo(riga_op, testo_vincolo):
    v = riga_op.get('vincoli', [])
    return testo_vincolo in v if isinstance(v, list) else False

if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # --- FILTRO OPERATORI VALIDI ---
    # Escludiamo chi ha nome "None", nome vuoto, o ore settimanali <= 0
    op_validi_df = edited_df[
        (edited_df['nome'].notna()) & 
        (edited_df['nome'].str.lower() != "none") & 
        (edited_df['nome'] != "") & 
        (edited_df['ore_sett'] > 0)
    ]
    
    nomi_op = op_validi_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi_op + ["ESTERNI"], columns=giorni_cols)
    
    ore_fatte = {nome: 0 for nome in nomi_op}
    ore_fatte["ESTERNI"] = 0

    # Limite massimo di ore mensili (ore settimanali * 4 settimane circa)
    limiti_ore = {r['nome']: r['ore_sett'] * 4.3 for _, r in op_validi_df.iterrows()}
    limiti_ore["ESTERNI"] = 999

    for g_idx, col in enumerate(giorni_cols):
        is_we = "Sat" in col or "Sun" in col
        oggi = []

        # 1. NOTTE (1 PERSONA) - 9 ore
        cand_n = [r['nome'] for _, r in op_validi_df.iterrows() if ha_vincolo(r, "Fa Notti")] + ["ESTERNI"]
        scelto_n = None
        
        for d in cand_n:
            if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                    scelto_n = d
        
        if not scelto_n:
            # Scegliamo chi non è in smonto e non ha superato il limite ore settimanali
            disp_n = [d for d in cand_n if (g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N") and (ore_fatte[d] + 9 <= limiti_ore.get(d, 999))]
            disp_n.sort(key=lambda x: ore_fatte[x])
            scelto_n = disp_n[0] if disp_n else "ESTERNI"
        
        res_df.at[scelto_n, col] = "N"
        ore_fatte[scelto_n] += 9
        oggi.append(scelto_n)

        # 2. MATTINA (2 PERSONE) - 7 ore
        cand_m = []
        for _, r in op_validi_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            if ore_fatte[n] + 7 > limiti_ore[n]: continue # Controllo tetto ore
            cand_m.append(n)
        
        cand_m.sort(key=lambda x: ore_fatte[x])
        for s in cand_m[:2]:
            res_df.at[s, col] = "M"
            ore_fatte[s] += 7
            oggi.append(s)

        # 3. POMERIGGIO (2 PERSONE) - 8 ore
        cand_p = []
        for _, r in op_validi_df.iterrows():
            n = r['nome']
            if n in oggi or (g_idx > 0 and res_df.at[n, giorni_cols[g_idx-1]] == "N"): continue
            if ha_vincolo(r, "No Pomeriggio") or ha_vincolo(r, "Solo Mattina"): continue
            if is_we and ha_vincolo(r, "No Weekend"): continue
            if ore_fatte[n] + 8 > limiti_ore[n]: continue # Controllo tetto ore
            cand_p.append(n)
        
        cand_p.sort(key=lambda x: ore_fatte[x])
        for s in cand_p[:2]:
            res_df.at[s, col] = "P"
            ore_fatte[s] += 8

    # --- RIMOZIONE RIGHE VUOTE DALLA VISUALIZZAZIONE ---
    # Se un operatore non ha ricevuto turni (perché a 0 ore), non lo mostriamo o mostriamo riga vuota
    res_df["ORE TOTALI"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    
    st.write("### 📅 Tabella Turni (Solo personale attivo)")
    st.dataframe(res_df)

    st.download_button("📥 Scarica Turni", res_df.to_csv().encode('utf-8'), "turni_aprile_filtrati.csv")
