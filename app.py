import streamlit as st
import pandas as pd
import calendar

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni Settimanale", layout="wide")
st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# Lista Vincoli
VINCOLI_LISTA = ["No Weekend", "Solo Notti", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"]

# Inizializzazione Dati con nomi puliti
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "vincoli": []}
    ]

st.subheader("👥 Configurazione Operatori (Ore Settimanali)")
# Tabella di input senza ore nel nome
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "nome": st.column_config.TextColumn("Nome Operatore"),
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=VINCOLI_LISTA),
        "ore": st.column_config.NumberColumn("Ore Settimanali", min_value=0)
    }
)

def puo_lavorare(riga_op, tipo_turno, is_weekend, ore_settimanali_attuali, durata_turno):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    
    # Controllo limite settimanale
    limite_settimanale = riga_op.get('ore', 0)
    if ore_settimanali_attuali + durata_turno > limite_settimanale:
        return False
    
    # Controllo vincoli
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
    
    # Pulizia dati per evitare AttributeError
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[(df_clean['nome'].notna()) & (df_clean['nome'] != "") & (df_clean['ore'] > 0)].copy()
    
    if op_validi.empty:
        st.error("Inserisci operatori con ore settimanali valide!")
    else:
        nomi_op = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
        
        ore_totali_mese = {n: 0 for n in nomi_op}
        ore_settimana_corrente = {n: 0 for n in nomi_op}

        for g_idx, col in enumerate(giorni_cols):
            giorno_del_mese = g_idx + 1
            wd_idx = calendar.weekday(anno, mese, giorno_del_mese)
            
            # Reset Lunedì (0)
            if wd_idx == 0:
                ore_settimana_corrente = {n: 0 for n in nomi_op}
            
            is_we = wd_idx >= 5
            oggi_occupati = []

            # 1. NOTTE (9h)
            cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_lavorare(r, "N", is_we, ore_settimana_corrente[r['nome']], 9)]
            scelto_n = None
            for d in cand_n:
                if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                    if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N": scelto_n = d
            
            if not scelto_n and cand_n:
                disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
                if disp_n:
                    disp_n.sort(key=lambda x: ore_totali_mese[x])
                    scelto_n = disp_n[0]
            
            if scelto_n:
                res_df.at[scelto_n, col] = "N"
                ore_settimana_corrente[scelto_n] += 9
                ore_totali_mese[scelto_n] += 9
                oggi_occupati.append(scelto_n)

            # 2. MATTINA (7h)
            cand_m = [n for n in nomi_op if n not in oggi_occupati]
            cand_m = [n for n in cand_m if puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "M", is_we, ore_settimana_corrente[n], 7)]
            cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_m.sort(key=lambda x: ore_totali_mese[x])
            for s in cand_m[:2]:
                res_df.at[s, col] = "M"
                ore_settimana_corrente[s] += 7
                ore_totali_mese[s] += 7
                oggi_occupati.append(s)

            # 3. POMERIGGIO (8h)
            cand_p = [n for n in nomi_op if n not in oggi_occupati]
            cand_p = [n for n in cand_p if puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "P", is_we, ore_settimana_corrente[n], 8)]
            cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_p.sort(key=lambda x: ore_totali_mese[x])
            for s in cand_p[:2]:
                res_df.at[s, col] = "P"
                ore_settimana_corrente[s] += 8
                ore_totali_mese[s] += 8

        res_df["ORE TOTALI MESE"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
        st.write("### 📅 Tabella Turni Generata")
        st.dataframe(res_df)
        
        st.write("### 📊 Riepilogo Ore Mensili")
        st.table(pd.DataFrame({"Contratto Sett.": op_validi.set_index('nome')['ore'], "Totale Mese": res_df["ORE TOTALI MESE"]}))
