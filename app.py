import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

st.set_page_config(page_title="Gestione Turni V13", layout="wide")
st.title("🗓️ Turnistica: Ciclo 2G+2N+S+R con Analisi Target")

# 1. DATABASE OPERATORI
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
    key="editor_v13"
)

def genera_turni():
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna()].copy()
    nomi = op_validi['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    # Stato: 0:Libero, 1:G1, 2:G2, 3:N1, 4:N2, 5:Smonto, 6:Riposo
    stati = {n: 0 for n in nomi}
    ore_effettive = {n: 0 for n in nomi}
    targets = {row['nome']: row['ore'] * 4 for _, row in op_validi.iterrows()}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi = []

        # A. PROSECUZIONE CICLI ESISTENTI (Priorità 1)
        for n in nomi:
            if stati[n] == 1: # Da G1 a G2
                turno = "M" if "no pomeriggio" in str(op_validi.set_index('nome').at[n, 'vincoli']).lower() else "P"
                res_df.at[n, col] = turno
                stati[n] = 2
                oggi.append(n)
                ore_effettive[n] += 7 if turno == "M" else 8
            elif stati[n] == 2: # Da G2 a N1
                res_df.at[n, col] = "N"
                stati[n] = 3
                oggi.append(n)
                ore_effettive[n] += 9
            elif stati[n] == 3: # Da N1 a N2
                res_df.at[n, col] = "N"
                stati[n] = 4
                oggi.append(n)
                ore_effettive[n] += 9
            elif stati[n] == 4: # Da N2 a Smonto
                stati[n] = 5
                oggi.append(n)
            elif stati[n] == 5: # Da Smonto a Riposo
                stati[n] = 0 # Torna libero
        
        # B. COPERTURA NOTTE (Se vuota, innesca ciclo)
        if res_df[col].tolist().count("N") < 1:
            candidati_n = [n for n in nomi if n not in oggi and stati[n] == 0 and "fa notti" in str(op_validi.set_index('nome').at[n, 'vincoli']).lower()]
            if is_we: candidati_n = [n for n in candidati_n if "no weekend" not in str(op_validi.set_index('nome').at[n, 'vincoli']).lower()]
            
            if candidati_n:
                # Scegli chi è più lontano dal target (%)
                scelto = min(candidati_n, key=lambda x: ore_effettive[x] / targets[x])
                res_df.at[scelto, col] = "N"
                stati[scelto] = 3
                oggi.append(scelto)
                ore_effettive[scelto] += 9

        # C. COPERTURA DIURNI (M=2, P=2)
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_mancanti = t_posti - res_df[col].tolist().count(t_tipo)
            for _ in range(posti_mancanti):
                candidati = [n for n in nomi if n not in oggi and stati[n] == 0]
                # Filtri vincoli
                candidati = [n for n in candidati if not (is_we and "no weekend" in str(op_validi.set_index('nome').at[n, 'vincoli']).lower())]
                if t_tipo == "M": candidati = [n for n in candidati if "no mattina" not in str(op_validi.set_index('nome').at[n, 'vincoli']).lower()]
                if t_tipo == "P": candidati = [n for n in candidati if "no pomeriggio" not in str(op_validi.set_index('nome').at[n, 'vincoli']).lower()]
                
                if candidati:
                    scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x])
                    res_df.at[scelto, col] = t_tipo
                    if "fa notti" in str(op_validi.set_index('nome').at[scelto, 'vincoli']).lower():
                        stati[scelto] = 1 # Inizia il ciclo 2G+2N
                    oggi.append(scelto)
                    ore_effettive[scelto] += t_ore

    return res_df, ore_effettive, targets

if st.button("🚀 GENERA E CALCOLA PERCENTUALI"):
    risultato, ore, targets = genera_turni()
    
    st.subheader("📅 Tabella Turni Ciclica")
    st.dataframe(risultato)
    
    # ANALISI BILANCIAMENTO (La parte che mancava)
    st.subheader("📊 3. Analisi Carico di Lavoro vs Target")
    analisi = pd.DataFrame({
        "Contratto Sett.": [edited_df.set_index('nome').at[n, 'ore'] for n in risultato.index],
        "Target Mensile (x4)": [targets[n] for n in risultato.index],
        "Ore Effettive": [ore[n] for n in risultato.index]
    }, index=risultato.index)
    
    # Calcolo Percentuale
    analisi["% Saturazione"] = (analisi["Ore Effettive"] / analisi["Target Mensile (x4)"] * 100).round(1)
    
    # Formattazione per colore
    def color_sat(val):
        color = 'red' if val > 110 else 'orange' if val < 80 else 'green'
        return f'color: {color}'

    st.table(analisi.style.applymap(color_sat, subset=['% Saturazione']))

    # VERIFICA COPERTURA 2-2-1
    st.subheader("✅ 4. Verifica Copertura Giornaliera")
    conteggi = [{"Giorno": c, "M": risultato[c].tolist().count("M"), "P": risultato[c].tolist().count("P"), "N": risultato[c].tolist().count("N")} for c in risultato.columns]
    st.table(pd.DataFrame(conteggi).set_index("Giorno").T)
