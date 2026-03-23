import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V15", layout="wide")
st.title("🗓️ Turnistica: Priorità Assoluta Copertura 2-2-1")

# Database Operatori
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
    key="editor_v15"
)

def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi')
    return output.getvalue()

def genera_turni():
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_data = edited_df[edited_df['nome'].notna()].copy()
    nomi = op_data['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_effettive = {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_data.iterrows()}
    
    # Tracking per la regola: 2 diurni -> 2 notti -> smonto -> riposo
    # Conserviamo lo stato dell'operatore
    stato_ciclo = {n: 0 for n in nomi} 

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # --- FASE 1: COPERTURA NOTTE (OBBLIGATORIA 1) ---
        # Prima controlliamo se qualcuno è già nel mezzo delle 2 notti
        percorso_notte = [n for n in nomi if stato_ciclo[n] == 4] # Era alla prima notte, ora DEVE fare la seconda
        
        for n in percorso_notte:
            res_df.at[n, col] = "N"
            stato_ciclo[n] = 5 # Passa allo smonto
            oggi.append(n)
            ore_effettive[n] += 9

        # Se la notte non è coperta, cerchiamo un nuovo notturnista
        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                v = str(op_data.set_index('nome').at[n, 'vincoli']).lower()
                if n not in oggi and "fa notti" in v and stato_ciclo[n] in [0, 6]:
                    if not (is_we and "no weekend" in v):
                        candidati_n.append(n)
            
            if candidati_n:
                scelto = min(candidati_n, key=lambda x: ore_effettive[x] / targets[x])
                res_df.at[scelto, col] = "N"
                stato_ciclo[scelto] = 4 # Segna che ha fatto la prima notte
                oggi.append(scelto)
                ore_effettive[scelto] += 9

        # --- FASE 2: COPERTURA DIURNI (OBBLIGATORI 2M + 2P) ---
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_coperti = res_df[col].tolist().count(t_tipo)
            for _ in range(t_posti - posti_coperti):
                candidati = []
                for n in nomi:
                    v = str(op_data.set_index('nome').at[n, 'vincoli']).lower()
                    if n not in oggi and stato_ciclo[n] in [0, 6]:
                        if is_we and "no weekend" in v: continue
                        if t_tipo == "M" and "no mattina" in v: continue
                        if t_tipo == "P" and "no pomeriggio" in v: continue
                        candidati.append(n)
                
                if candidati:
                    scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x])
                    res_df.at[scelto, col] = t_tipo
                    # Se è un notturnista, facciamogli iniziare il ciclo dei 2 diurni
                    if "fa notti" in str(op_data.set_index('nome').at[scelto, 'vincoli']).lower():
                        stato_ciclo[scelto] = 1 # Inizia Giorno 1
                    else:
                        stato_ciclo[scelto] = 0 # Operatore diurno semplice
                    oggi.append(scelto)
                    ore_effettive[scelto] += t_ore

        # --- FASE 3: AGGIORNAMENTO STATI PER IL GIORNO DOPO ---
        for n in nomi:
            if n not in oggi:
                if stato_ciclo[n] == 5: stato_ciclo[n] = 6 # Da smonto a riposo
                elif stato_ciclo[n] == 6: stato_ciclo[n] = 0 # Da riposo a libero
                # Se un notturnista era a metà ciclo diurno (1 o 2) ma oggi non ha lavorato, resetta o resta in attesa? 
                # Per ora lasciamo che il ciclo riparta se saltano un giorno.

    return res_df, ore_effettive, targets

if st.button("🚀 GENERA CON COPERTURA RIGIDA 2-2-1"):
    risultato, ore, targets = genera_turni()
    
    st.subheader("📅 Tabella Turni (Priorità Copertura)")
    st.dataframe(risultato)
    
    # Analisi Percentuali
    st.subheader("📊 Analisi Saturazione")
    analisi = pd.DataFrame({
        "Target": [targets[n] for n in risultato.index],
        "Effettive": [ore[n] for n in risultato.index]
    }, index=risultato.index)
    analisi["% Saturazione"] = (analisi["Effettive"] / analisi["Target"] * 100).round(1)
    st.table(analisi.style.background_gradient(subset=['% Saturazione'], cmap='RdYlGn'))

    # Verifica Copertura (DEVE ESSERE SEMPRE 2-2-1)
    st.subheader("✅ Verifica Copertura Giornaliera")
    conteggi = []
    for c in risultato.columns:
        l = risultato[c].tolist()
        conteggi.append({"Giorno": c, "M": l.count("M"), "P": l.count("P"), "N": l.count("N")})
    
    df_check = pd.DataFrame(conteggi).set_index("Giorno").T
    st.table(df_check)

    # Download
    excel_file = to_excel(risultato, analisi)
    st.download_button("📥 Scarica Excel", excel_file, "turni_221.xlsx")
