import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gestione Turni V24", layout="wide")
st.title("🗓️ Generatore Turni: Assenze e Rispetto Smonto Notte")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df, mese_nome, anno):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR: SELEZIONE PERIODO ---
st.sidebar.header("Configurazione Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

mese_scelto_nome = st.sidebar.selectbox("Seleziona Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Seleziona Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

# --- 1. DATABASE OPERATORI ---
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

# --- 2. GESTIONE ASSENZE ---
if 'assenze_periodi' not in st.session_state:
    st.session_state.assenze_periodi = []

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("👥 Operatori e Vincoli")
    op_df = st.data_editor(
        pd.DataFrame(st.session_state.operatori), 
        num_rows="dynamic",
        key="editor_op_v24",
        column_config={
            "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "Fa Notti", "No Mattina", "No Pomeriggio"])
        }
    )

with col2:
    st.subheader("🚫 Periodi di Assenza (Blocca Turno e Smonto)")
    periodi_df = st.data_editor(
        pd.DataFrame(st.session_state.assenze_periodi, columns=["Operatore", "Dal_Giorno", "Al_Giorno"]),
        num_rows="dynamic",
        key="editor_periodi_v24",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Operatore", options=op_df['nome'].tolist()),
            "Dal_Giorno": st.column_config.NumberColumn("Dal", min_value=1, max_value=31),
            "Al_Giorno": st.column_config.NumberColumn("Al", min_value=1, max_value=31)
        }
    )

def get_giorni_vietati(nome, df_periodi):
    vietati = set()
    for _, row in df_periodi.iterrows():
        if row['Operatore'] == nome and pd.notna(row['Dal_Giorno']) and pd.notna(row['Al_Giorno']):
            for g in range(int(row['Dal_Giorno']), int(row['Al_Giorno']) + 1):
                vietati.add(g)
    return vietati

# --- 3. LOGICA DI GENERAZIONE ---
def genera_turni_v24(anno, mese, df_periodi):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    nomi = op_df['nome'].tolist()
    res_df = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    
    ore_effettive = {n: 0 for n in nomi}
    conteggio_notti = {n: 0 for n in nomi} 
    targets = {row['nome']: row['ore'] * 4 for _, row in op_df.iterrows()}
    stato_notte = {n: 0 for n in nomi} 

    for g_idx, col in enumerate(giorni_cols):
        g_num = g_idx + 1
        is_we = calendar.weekday(anno, mese, g_num) >= 5
        oggi = []

        # --- A. GESTIONE NOTTE ---
        for n in nomi:
            vietati = get_giorni_vietati(n, df_periodi)
            if stato_notte[n] == 1:
                # Se oggi deve fare la 2° notte ma domani (g_num + 1) è assente (SMONTO), non può farla
                # Oppure se è assente oggi stesso
                if g_num in vietati or (g_num + 1) in vietati:
                    stato_notte[n] = 0 
                    continue
                res_df.at[n, col] = "N"
                stato_notte[n] = 0
                oggi.append(n)
                ore_effettive[n] += 9
                conteggio_notti[n] += 1

        if res_df[col].tolist().count("N") < 1:
            candidati_n = []
            for n in nomi:
                v = str(op_df[op_df['nome'] == n]['vincoli'].values[0]).lower()
                vietati = get_giorni_vietati(n, df_periodi)
                # Per iniziare una notte (che dura 2 gg + smonto), non deve essere assente oggi, domani e dopodomani
                if n not in oggi and "fa notti" in v:
                    if g_num not in vietati and (g_num + 1) not in vietati and (g_num + 2) not in vietati:
                        if not (is_we and "no weekend" in v):
                            candidati_n.append(n)
            
            if candidati_n:
                scelto = min(candidati_n, key=lambda x: (conteggio_notti[x], ore_effettive[x] / targets[x] if targets[x]>0 else 0))
                res_df.at[scelto, col] = "N"
                stato_notte[scelto] = 1 
                oggi.append(scelto)
                ore_effettive[scelto] += 9
                conteggio_notti[scelto] += 1

        # --- B. DIURNI ---
        for t_tipo, t_ore, t_posti in [("M", 7, 2), ("P", 8, 2)]:
            posti_assegnati = 0
            while posti_assegnati < t_posti:
                candidati = []
                for n in nomi:
                    v = str(op_df[op_df['nome'] == n]['vincoli'].values[0]).lower()
                    vietati = get_giorni_vietati(n, df_periodi)
                    if n not in oggi and g_num not in vietati:
                        if is_we and "no weekend" in v: continue
                        if t_tipo == "M" and "solo pomeriggio" in v: continue
                        if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): continue
                        candidati.append(n)
                if not candidati: break 
                scelto = min(candidati, key=lambda x: ore_effettive[x] / targets[x] if targets[x]>0 else 0)
                res_df.at[scelto, col] = t_tipo
                oggi.append(scelto)
                ore_effettive[scelto] += t_ore
                posti_assegnati += 1

    return res_df, ore_effettive, targets, conteggio_notti

# --- 4. OUTPUT ---
if st.button(f"🚀 GENERA TURNI {mese_scelto_nome.upper()}"):
    risultato, ore, targets, notti = genera_turni_v24(anno_scelto, mese_scelto_num, periodi_df)
    st.subheader(f"📅 Calendario {mese_scelto_nome}")
    st.dataframe(risultato)
    
    # Analisi
    analisi = pd.DataFrame({"Notti": [notti[n] for n in risultato.index], "Ore": [ore[n] for n in risultato.index], "%": [(ore[n]/targets[n]*100) if targets[n]>0 else 0 for n in risultato.index]}, index=risultato.index).round(1)
    st.table(analisi)

    # Verifica
    check = [{"G": c, "M": risultato[c].tolist().count("M"), "P": risultato[c].tolist().count("P"), "N": risultato[c].tolist().count("N")} for c in risultato.columns]
    st.write("**Copertura Giornaliera:**")
    st.table(pd.DataFrame(check).set_index("G").T)

    # Excel
    excel_data = to_excel(risultato, analisi, mese_scelto_nome, anno_scelto)
    st.download_button("📥 Scarica Excel", data=excel_data, file_name=f"turni_{mese_scelto_nome}.xlsx")
