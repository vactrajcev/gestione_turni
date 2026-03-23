import streamlit as st
import pandas as pd
import calendar

# Configurazione della pagina
st.set_page_config(page_title="Gestione Turni Professionale", layout="wide")

st.title("🗓️ Generatore Turni Professionale - Aprile 2026")

# --- DATABASE OPERATORI INIZIALE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B. (30)", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J. (28)", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M. (25)", "ore": 25, "vincoli": []}
    ]

# Pulsante per resettare ai nomi originali
if st.sidebar.button("Reset Dati Originali"):
    st.session_state.operatori = [
        {"nome": "NERI ELENA (38)", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA (38)", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H. (38)", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA (38)", "ore": 38, "vincoli": []}
    ]
    st.rerun()

st.subheader("👥 Configurazione Personale e Vincoli")
st.write("Modifica i nomi, le ore o aggiungi/rimuovi i vincoli direttamente nella tabella.")

# Tabella interattiva per l'utente
edited_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")

# --- FUNZIONE LOGICA VINCOLI (MIGLIORATA) ---
def puo_lavorare(riga_op, tipo_turno, is_weekend):
    v_raw = riga_op.get('vincoli', [])
    v = [str(item).lower().strip() for item in v_raw] if isinstance(v_raw, list) else []
    
    # 1. Blocco Weekend
    if is_weekend and "no weekend" in v:
        return False
    
    # 2. Controllo Esclusività ("Solo")
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    # 3. Controllo Turno Notte
    if tipo_turno == "N":
        if "no notte" in v: return False
        return "fa notti" in v or "solo notti" in v
    
    # 4. Controllo Divieti Generici
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    
    return True

# --- GENERATORE ---
if st.button("🚀 GENERA TURNI BILANCIATI"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    # Pulizia e Filtro Operatori
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[(df_clean['nome'].notna()) & (df_clean['nome'] != "") & (df_clean['ore'] > 0)].copy()
    
    if op_validi.empty:
        st.error("Aggiungi almeno un operatore con ore maggiori di 0!")
    else:
        nomi_op = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi_op, columns=giorni_cols)
        ore_fatte = {nome: 0 for nome in nomi_op}

        for g_idx, col in enumerate(giorni_cols):
            # Calcolo weekend matematico
            is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
            oggi_occupati = []

            # A. TURNO NOTTE (1 Persona)
            cand_n = [r['nome'] for _, r in op_validi.iterrows() if puo_lavorare(r, "N", is_we)]
            scelto_n = None
            # Priorità a chi deve chiudere il blocco di 2 notti
            for d in cand_n:
                if g_idx > 0 and res_df.at[d, giorni_cols[g_idx-1]] == "N":
                    if g_idx == 1 or res_df.at[d, giorni_cols[g_idx-2]] != "N":
                        scelto_n = d
            
            if not scelto_n and cand_n:
                # Evita chi ha fatto la notte ieri (riposo smonto)
                disp_n = [d for d in cand_n if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
                if disp_n:
                    disp_n.sort(key=lambda x: ore_fatte[x])
                    scelto_n = disp_n[0]
            
            if scelto_n:
                res_df.at[scelto_n, col] = "N"
                ore_fatte[scelto_n] += 9
                oggi_occupati.append(scelto_n)

            # B. TURNO MATTINA (2 Persone)
            cand_m = [n for n in nomi_op if n not in oggi_occupati and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "M", is_we)]
            # Protezione smonto: chi ha finito la notte non lavora oggi
            cand_m = [d for d in cand_m if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_m.sort(key=lambda x: ore_fatte[x])
            for s in cand_m[:2]:
                res_df.at[s, col] = "M"
                ore_fatte[s] += 7
                oggi_occupati.append(s)

            # C. TURNO POMERIGGIO (2 Persone)
            cand_p = [n for n in nomi_op if n not in oggi_occupati and puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], "P", is_we)]
            cand_p = [d for d in cand_p if g_idx == 0 or res_df.at[d, giorni_cols[g_idx-1]] != "N"]
            cand_p.sort(key=lambda x: ore_fatte[x])
            for s in cand_p[:2]:
                res_df.at[s, col] = "P"
                ore_fatte[s] += 8

        # --- RISULTATI FINALI ---
        res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
        
        st.write("### 📅 Tabella Turni Finale")
        st.dataframe(res_df.style.highlight_max(axis=0, color='lightgreen'))

        st.write("### ✅ Verifica Copertura (Standard 2-2-1)")
        check = pd.DataFrame({
            "M": [res_df[c].tolist().count("M") for c in giorni_cols],
            "P": [res_df[c].tolist().count("P") for c in giorni_cols],
            "N": [res_df[c].tolist().count("N") for c in giorni_cols]
        }, index=giorni_cols).T
        st.table(check)

        # Download
        csv = res_df.to_csv().encode('utf-8')
        st.download_button("📥 Scarica in Excel (CSV)", csv, "turni_aprile.csv", "text/csv")
