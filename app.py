import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V12", layout="wide")
st.title("🗓️ Turnistica: 2 Diurni + 2 Notti + Smonto + Riposo")

# Database Iniziale
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

edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"])
    },
    key="editor_v12"
)

def genera_turni():
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna()].copy()
    nomi = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    # Stato speciale per i notturnisti: tiene traccia di dove si trovano nella sequenza
    # 0: Libero, 1: Giorno1, 2: Giorno2, 3: Notte1, 4: Notte2, 5: Smonto, 6: Riposo
    stati = {n: 0 for n in nomi}
    ore_effettive = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        assegnati_oggi = []

        # 1. GESTIONE SEQUENZE OBBLIGATORIE (Chi è già a metà del ciclo)
        for n in nomi:
            if stati[n] == 1: # Era Giorno 1 -> Deve fare Giorno 2
                turno = "M" if "no pomeriggio" in str(op_validi.set_index('nome').at[n, 'vincoli']) else "P"
                res_df.at[n, col] = turno
                stati[n] = 2
                assegnati_oggi.append(n)
                ore_effettive[n] += 7 if turno == "M" else 8
            elif stati[n] == 2: # Era Giorno 2 -> Deve fare Notte 1
                res_df.at[n, col] = "N"
                stati[n] = 3
                assegnati_oggi.append(n)
                ore_effettive[n] += 9
            elif stati[n] == 3: # Era Notte 1 -> Deve fare Notte 2
                res_df.at[n, col] = "N"
                stati[n] = 4
                assegnati_oggi.append(n)
                ore_effettive[n] += 9
            elif stati[n] == 4: # Era Notte 2 -> Smonto
                stati[n] = 5
                assegnati_oggi.append(n)
            elif stati[n] == 5: # Era Smonto -> Riposo
                stati[n] = 0 # Torna libero dopo il riposo

        # 2. COPERTURA NOTTE (Se manca)
        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                if n not in assegnati_oggi and stati[n] == 0:
                    v = str(op_validi.set_index('nome').at[n, 'vincoli'])
                    if "fa notti" in v.lower() and not (is_we and "no weekend" in v.lower()):
                        candidati_n.append(n)
            
            if candidati_n:
                # Scegli chi ha meno ore per bilanciare
                scelto = min(candidati_n, key=lambda x: ore_effettive[x])
                res_df.at[scelto, col] = "N"
                stati[scelto] = 3 # Inizia dalla notte (sfalsamento)
                assegnati_oggi.append(scelto)
                ore_effettive[scelto] += 9

        # 3. COPERTURA DIURNI (M=2, P=2)
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_mancanti = t_posti - res_df[col].tolist().count(t_tipo)
            for _ in range(posti_mancanti):
                candidati = []
                for n in nomi:
                    if n not in assegnati_oggi and stati[n] == 0:
                        v = str(op_validi.set_index('nome').at[n, 'vincoli']).lower()
                        if is_we and "no weekend" in v: continue
                        if t_tipo == "M" and "no mattina" in v: continue
                        if t_tipo == "P" and "no pomeriggio" in v: continue
                        candidati.append(n)
                
                if candidati:
                    scelto = min(candidati, key=lambda x: ore_effettive[x])
                    res_df.at[scelto, col] = t_tipo
                    # Se è un notturnista, facciamolo entrare nella sequenza Giorno->Giorno->Notte
                    if "fa notti" in str(op_validi.set_index('nome').at[scelto, 'vincoli']).lower():
                        stati[scelto] = 1
                    assegnati_oggi.append(scelto)
                    ore_effettive[scelto] += t_ore

    return res_df, ore_effettive

if st.button("🚀 GENERA CICLO 2+2+SMONTO+RIPOSO"):
    risultato, ore = genera_turni()
    st.subheader("📅 Tabella Turni Ciclica")
    st.dataframe(risultato)
    
    # Verifica Copertura
    conteggi = [{"Giorno": c, "M": risultato[c].tolist().count("M"), "P": risultato[c].tolist().count("P"), "N": risultato[c].tolist().count("N")} for c in risultato.columns]
    st.subheader("✅ Verifica Copertura 2-2-1")
    st.table(pd.DataFrame(conteggi).set_index("Giorno").T)

    # Analisi Ore
    st.subheader("📊 Bilanciamento Ore")
    analisi = pd.DataFrame({"Ore Effettive": ore.values()}, index=ore.keys())
    st.table(analisi)
