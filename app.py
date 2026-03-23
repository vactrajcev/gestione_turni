import streamlit as st
import pandas as pd
import calendar

# --- CONFIGURAZIONE E TITOLO ---
st.set_page_config(page_title="Backup Turni Funzionante", layout="wide")
st.title("🗓️ Generatore Turni - Versione Stabile (Backup)")

# --- COSTANTI ---
VINCOLI_LISTA = ["No Weekend", "Solo Notti", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"]

# --- INIZIALIZZAZIONE STATO ---
if 'operatori_backup' not in st.session_state:
    st.session_state.operatori_backup = [
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "vincoli": []}
    ]

# --- INTERFACCIA INPUT ---
st.subheader("👥 Configurazione Operatori")
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori_backup),
    num_rows="dynamic",
    column_config={
        "nome": st.column_config.TextColumn("Nome Operatore", width="large"),
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=VINCOLI_LISTA, width="medium"),
        "ore": st.column_config.NumberColumn("Ore Settimanali", min_value=0)
    },
    key="editor_backup_stabile"
)

# --- LOGICA DI CONTROLLO ---
def puo_lavorare(riga_op, tipo_turno, is_weekend, ore_sett_attuali, durata_turno):
    v = [str(i).lower().strip() for i in riga_op.get('vincoli', [])] if isinstance(riga_op.get('vincoli'), list) else []
    limite = riga_op.get('ore', 0)
    
    if ore_sett_attuali + durata_turno > limite: return False
    if is_weekend and "no weekend" in v: return False
    if "solo notti" in v and tipo_turno != "N": return False
    if "solo mattina" in v and tipo_turno != "M": return False
    if "solo pomeriggio" in v and tipo_turno != "P": return False
    
    if tipo_turno == "N":
        return "fa notti" in v or "solo notti" in v
    
    if tipo_turno == "M" and "no mattina" in v: return False
    if tipo_turno == "P" and "no pomeriggio" in v: return False
    return True

# --- MOTORE DI GENERAZIONE ---
if st.button("🚀 GENERA TABELLA"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    df_clean = edited_df.copy()
    df_clean['ore'] = pd.to_numeric(df_clean['ore'], errors='coerce').fillna(0)
    op_validi = df_clean[df_clean['nome'].notna() & (df_clean['nome'] != "")].copy()
    
    if op_validi.empty:
        st.error("Nessun operatore inserito!")
    else:
        nomi = op_validi['nome'].tolist()
        res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
        ore_tot_mese = {n: 0 for n in nomi}
        ore_sett_curr = {n: 0 for n in nomi}

        for g_idx, col in enumerate(giorni_cols):
            wd = calendar.weekday(anno, mese, g_idx + 1)
            if wd == 0: ore_sett_curr = {n: 0 for n in nomi} # Reset Lunedì
            
            is_we = wd >= 5
            occupati_oggi = []

            # Priorità Turni: Notte (9h), poi Mattina (7h), poi Pomeriggio (8h)
            for turno, ore_t in [("N", 9), ("M", 7), ("P", 8)]:
                posti = 1 if turno == "N" else 2
                candidati = [n for n in nomi if n not in occupati_oggi]
                
                # Applica vincoli e controllo ore
                validi = [n for n in candidati if puo_lavorare(op_validi[op_validi['nome']==n].iloc[0], turno, is_we, ore_sett_curr[n], ore_t)]
                
                # Protezione Smonto Notte
                validi = [v for v in validi if g_idx == 0 or res_df.at[v, giorni_cols[g_idx-1]] != "N"]
                
                # Bilanciamento: scegli chi ha lavorato meno nel mese
                validi.sort(key=lambda x: ore_tot_mese[x])
                
                for s in validi[:posti]:
                    if res_df.at[s, col] == "-":
                        res_df.at[s, col] = turno
                        ore_sett_curr[s] += ore_t
                        ore_tot_mese[s] += ore_t
                        occupati_oggi.append(s)

        res_df["TOT ORE"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
        st.dataframe(res_df)
        st.success("Backup salvato e tabella generata correttamente.")
