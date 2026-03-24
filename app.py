import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE INTERFACCIA ---
st.set_page_config(page_title="Gestione Turni V65.6", layout="wide", page_icon="⚖️")

DB_FILE = "database_turni_v65.json"

def carica_dati():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return None
    return None

def salva_dati(operatori):
    with open(DB_FILE, "w") as f:
        json.dump(operatori, f)

def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- INIZIALIZZAZIONE DATI ---
if 'operatori' not in st.session_state:
    dati = carica_dati()
    if dati:
        st.session_state.operatori = dati
    else:
        st.session_state.operatori = [
            {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
            {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["Solo Mattina"]},
            {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
            {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
            {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
            {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
            {"nome": "PALMIERI J.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []},
            {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []}
        ]

st.title("⚖️ Sistema Turni V65.6 - Full Code")

# --- SEZIONE CONFIGURAZIONE ---
with st.expander("⚙️ Gestione Squadra e Parametri Database"):
    col_config = {
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli Personali", 
            options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]
        ),
        "fa_notti": st.column_config.CheckboxColumn("Abilita Notti"),
        "max_notti": st.column_config.NumberColumn("Max Notti/Mese", min_value=0, max_value=15)
    }
    
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="main_editor", column_config=col_config)
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    
    if st.button("💾 SALVA CONFIGURAZIONE"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Database aggiornato con successo!")

    st.subheader("🤝 Incompatibilità (Evita turni contemporanei)")
    inc_df = st.data_editor(
        pd.DataFrame(columns=["Op A", "Op B"]), 
        num_rows="dynamic", 
        column_config={
            "Op A": st.column_config.SelectboxColumn("Operatore 1", options=lista_nomi),
            "Op B": st.column_config.SelectboxColumn("Operatore 2", options=lista_nomi)
        }
    )

col_left, col_right = st.columns(2)
with col_left:
    st.subheader("🚫 Registro Assenze")
    ass_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Dal", "Al"]), 
        num_rows="dynamic",
        column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)}
    )
with col_right:
    st.subheader("⭐ Preferenze e Blocchi")
    pref_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), 
        num_rows="dynamic",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
            "Turno": st.column_config.SelectboxColumn("Tipo", options=["M", "P", "N"])
        }
    )

# --- MOTORE DI CALCOLO PROFESSIONALE ---
def genera_piano_completo(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    
    tabella = pd.DataFrame("-", index=nomi, columns=giorni_cols)
    info_op = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    
    # Contatori e Stati
    ore_tot, notti_tot = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    stato_notte, cons_lavoro = {n: 0 for n in nomi}, {n: 0 for n in nomi}

    for g in range(1, num_g + 1):
        wd = calendar.weekday(anno, mese, g)
        col = giorni_cols[g-1]
        is_weekend = wd >= 5
        occupati_oggi = []

        # 1. REGOLA 6 GIORNI: Riposo forzato (Cella vuota)
        for n in nomi:
            if cons_lavoro[n] >= 6:
                tabella.at[n, col] = " "
                occupati_oggi.append(n)
                cons_lavoro[n] = 0

        # 2. GESTIONE PREFERENZE
        prefs = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in prefs.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occupati_oggi:
                tabella.at[n, col] = t
                occupati_oggi.append(n)
                ore_tot[n] += (9 if t == "N" else 7 if t == "M" else 8)
                cons_lavoro[n] += 1
                if t == "N": 
                    notti_tot[n] += 1
                    stato_notte[n] = 1

        # 3. LOGICA NOTTE (Ciclo 1N -> Smonto -> Riposo)
        notte_assegnata = (tabella[col] == "N").any()
        for n in nomi:
            if n in occupati_oggi: continue
            if stato_notte[n] == 1: # Fase Smonto
                if not notte_assegnata and info_op[n]['fa_notti'] and notti_tot[n] < info_op[n]['max_notti']:
                    tabella.at[n, col] = "N"
                    occupati_oggi.append(n)
                    ore_tot[n] += 9
                    notti_tot[n] += 1
                    stato_notte[n] = 2 # Prossimo giorno sarà smonto puro
                    cons_lavoro[n] += 1
                    notte_assegnata = True
                else:
                    tabella.at[n, col] = " "
                    occupati_oggi.append(n)
                    stato_notte[n] = 3
                    cons_lavoro[n] = 0
            elif stato_notte[n] in [2, 3]:
                tabella.at[n, col] = " "
                occupati_oggi.append(n)
                stato_notte[n] = 3 if stato_notte[n] == 2 else 0
                cons_lavoro[n] = 0

        # 4. RIEMPIMENTO TURNI MANCANTI (2M, 2P, 1N)
        for t_tipo, target_qta in [("N", 1), ("M", 2), ("P", 2)]:
            while tabella[col].tolist().count(t_tipo) < target_qta:
                candidati = [n for n in nomi if n not in occupati_oggi]
                filtrati = []
                
                for n in candidati:
                    v = [vinc.lower() for vinc in info_op[n].get('vincoli', [])]
                    ok = True
                    # Assenze
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    # Vincoli Notti
                    if t_tipo == "N" and (not info_op[n]['fa_notti'] or notti_tot[n] >= info_op[n]['max_notti']): ok = False
                    # Vincoli Orari
                    if is_weekend and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    # Incompatibilità
                    for occ in occupati_oggi:
                        if tabella.at[occ, col] == t_tipo:
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==occ)) | ((inc_df['Op A']==occ) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: filtrati.append(n)
                
                if not filtrati: break
                scelto = min(filtrati, key=lambda x: ore_tot[x]/(info_op[x]['ore']*4) if info_op[x]['ore']>0 else 1)
                tabella.at[scelto, col] = t_tipo
                occupati_oggi.append(scelto)
                ore_tot[scelto] += (9 if t_tipo == "N" else 7 if t_tipo == "M" else 8)
                cons_lavoro[scelto] += 1
                if t_tipo == "N": 
                    notti_tot[scelto] = notti_tot.get(scelto, 0) + 1
                    stato_notte[scelto] = 1

        # Reset lavoro consecutivo per chi è a riposo
        for n in nomi:
            if tabella.at[n, col] in ["-", " ", "R"]: cons_lavoro[n] = 0

    return tabella, ore_tot, notti_tot, info_op

# --- GENERAZIONE OUTPUT ---
mesi_nomi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
sel_mese = st.sidebar.selectbox("Mese", mesi_nomi, index=datetime.now().month - 1)
sel_anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA PIANO V65.6"):
    tab_risultato, ore_f, notti_f, info_f = genera_piano_completo(sel_anno, mesi_nomi.index(sel_mese) + 1)
    
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab_risultato, use_container_width=True)
    
    # Verifica Copertura con Ore e Totale Mese
    st.subheader("✅ Verifica Copertura Mensile")
    cop_data = []
    for c in tab_risultato.columns:
        m, p, n = tab_risultato[c].tolist().count("M"), tab_risultato[c].tolist().count("P"), tab_risultato[c].tolist().count("N")
        cop_data.append({"Giorno": c, "M": m, "P": p, "N": n, "Ore": (m*7)+(p*8)+(n*9)})
    cop_df = pd.DataFrame(cop_data).set_index("Giorno").T
    cop_df["TOTALE MESE"] = cop_df.sum(axis=1)
    st.table(cop_df)
    
    # Analisi Squadra con Totali
    st.subheader("📊 Analisi Carico di Lavoro")
    analisi_list = []
    for n in tab_risultato.index:
        targ = info_f[n]['ore']*4
        analisi_list.append({
            "Operatore": n, "Notti": notti_f[n], "Max N": info_f[n]['max_notti'],
            "Ore Effettive": ore_f[n], "Target Ore": targ, 
            "Saturazione %": round((ore_f[n]/targ*100), 1) if targ > 0 else 0
        })
    an_df = pd.DataFrame(analisi_list).set_index("Operatore")
    
    riga_tot = pd.DataFrame({
        "Notti": [an_df["Notti"].sum()], "Max N": [an_df["Max N"].sum()],
        "Ore Effettive": [an_df["Ore Effettive"].sum()], "Target Ore": [an_df["Target Ore"].sum()],
        "Saturazione %": [round((an_df["Ore Effettive"].sum()/an_df["Target Ore"].sum()*100), 1) if an_df["Target Ore"].sum()>0 else 0]
    }, index=["TOTALI SQUADRA"])
    
    final_analisi = pd.concat([an_df, riga_tot])
    st.table(final_analisi)
    
    st.download_button("📥 Esporta in Excel", data=to_excel(tab_risultato, final_analisi), file_name=f"Turni_{sel_mese}_{sel_anno}.xlsx")
