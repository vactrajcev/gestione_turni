import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V20", layout="wide")
st.title("🗓️ Generatore Turni Professionale (2-2-1 + Equità)")

# --- 1. FUNZIONE EXPORT EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    try:
        # Assicurati che 'xlsxwriter' sia presente nel file requirements.txt
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tabella Turni')
            analisi_df.to_excel(writer, sheet_name='Analisi Equità')
        return output.getvalue()
    except Exception as e:
        st.error(f"Errore nella generazione Excel: {e}")
        return None

# --- 2. DATABASE OPERATORI ---
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

op_data = st.data_editor(
    pd.DataFrame(st.session_state.operatori), 
    num_rows="dynamic",
    column_config={
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli", 
            options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"]
        )
    }
)

# --- 3. LOGICA DI GENERAZIONE ---
def genera_turni_final():
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    nomi = op_data['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_effettive = {n: 0 for n in nomi}
    conteggio_notti = {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_data.iterrows()}
    # Stato ciclo: 0:libero, 1:G1, 2:G2, 3:N1, 4:N2, 5:Smonto
    stati = {n: 0 for n in nomi}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # A. PROSECUZIONE CICLI (Priorità ai turni già iniziati)
        for n in nomi:
            v_list = [str(x).lower() for x in (op_data.set_index('nome').at[n, 'vincoli'] if isinstance(op_data.set_index('nome').at[n, 'vincoli'], list) else [])]
            
            if stati[n] == 1: # G1 -> G2
                turno = "M" if "no pomeriggio" in v_list else "P"
                res_df.at[n, col] = turno
                stati[n] = 2
                oggi.append(n)
                ore_effettive[n] += 7 if turno == "M" else 8
            elif stati[n] == 2: # G2 -> N1
                res_df.at[n, col] = "N"
                stati[n] = 3
                oggi.append(n)
                ore_effettive[n] += 9
                conteggio_notti[n] += 1
            elif stati[n] == 3: # N1 -> N2
                res_df.at[n, col] = "N"
                stati[n] = 4
                oggi.append(n)
                ore_effettive[n] += 9
                conteggio_notti[n] += 1
            elif stati[n] == 4: # N2 -> Smonto
                stati[n] = 5
                oggi.append(n)
            elif stati[n] == 5: # Smonto -> Libero
                stati[n] = 0

        # B. COPERTURA NOTTE (Assicura 1 N ogni giorno)
        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                v_list = [str(x).lower() for x in (op_data.set_index('nome').at[n, 'vincoli'] if isinstance(op_data.set_index('nome').at[n, 'vincoli'], list) else [])]
                if n not in oggi and stati[n] == 0 and "fa notti" in v_list:
                    if not (is_we and "no weekend" in v_list):
                        candidati_n.append(n)
            
            if candidati_n:
                # Sceglie chi ha fatto meno notti in totale
                scelto = min(candidati_n, key=lambda x: (conteggio_notti[x], ore_effettive[x]/targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = "N"
                stati[scelto] = 3 # Inizia dalla prima notte
                oggi.append(scelto)
                ore_effettive[scelto] += 9
                conteggio_notti[scelto] += 1

        # C. COPERTURA DIURNI (2 Mattina + 2 Pomeriggio)
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_mancanti = t_posti - res_df[col].tolist().count(t_tipo)
            for _ in range(posti_mancanti):
                candidati = []
                for n in nomi:
                    v_list = [str(x).lower() for x in (op_data.set_index('nome').at[n, 'vincoli'] if isinstance(op_data.set_index('nome').at[n, 'vincoli'], list) else [])]
                    if n not in oggi and stati[n] == 0:
                        if is_we and "no weekend" in v_list: continue
                        if t_tipo == "M" and "solo pomeriggio" in v_list: continue
                        if t_tipo == "P" and ("solo mattina" in v_list or "no pomeriggio" in v_list): continue
                        candidati.append(n)
                
                if candidati:
                    scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x] if targets[x]>0 else 0)
                    res_df.at[scelto, col] = t_tipo
                    v_list = [str(x).lower() for x in (op_data.set_index('nome').at[scelto, 'vincoli'] if isinstance(op_data.set_index('nome').at[scelto, 'vincoli'], list) else [])]
                    if "fa notti" in v_list:
                        stati[scelto] = 1 # Inizia il ciclo G1
                    oggi.append(scelto)
                    ore_effettive[scelto] += t_ore

    return res_df, ore_effettive, targets, conteggio_notti

# --- 4. INTERFACCIA E DOWNLOAD ---
if st.button("🚀 GENERA TURNI E SCARICA EXCEL"):
    risultato, ore, targets, notti = genera_turni_final()
    
    st.subheader("📅 Tabella Turni (Copertura 2-2-1)")
    st.dataframe(risultato)
    
    st.subheader("📊 Analisi Equità Notti e Ore")
    analisi = pd.DataFrame({
        "Notti Svolte": [notti[n] for n in risultato.index],
        "Ore Effettive": [ore[n] for n in risultato.index],
        "Target Mensile": [targets[n] for n in risultato.index],
        "% Saturazione": [(ore[n]/targets[n]*100) if targets[n]>0 else 0 for n in risultato.index]
    }, index=risultato.index).round(1)
    st.table(analisi)

    st.subheader("✅ Verifica Copertura")
    check_data = []
    for c in risultato.columns:
        check_data.append({
            "Giorno": c, 
            "M": risultato[c].tolist().count("M"), 
            "P": risultato[c].tolist().count("P"), 
            "N": risultato[c].tolist().count("N")
        })
    st.table(pd.DataFrame(check_data).set_index("Giorno").T)

    # Pulsante di Download
    file_ex = to_excel(risultato, analisi)
    if file_ex:
        st.download_button(
            label="📥 Scarica File Excel",
            data=file_ex,
            file_name="turni_equi_aprile_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
