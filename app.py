import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V65.1", layout="wide", page_icon="⚖️")

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

# --- INIZIALIZZAZIONE SESSIONE ---
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

st.title("⚖️ Sistema Turni V65.1 - Full Interface")

# --- AREA GESTIONE DATI ---
with st.expander("⚙️ Configurazione Squadra e Database"):
    # Editor Operatori con Menu Vincoli
    op_df = st.data_editor(
        pd.DataFrame(st.session_state.operatori), 
        num_rows="dynamic", 
        key="editor_op",
        column_config={
            "vincoli": st.column_config.MultiselectColumn(
                "Vincoli", 
                options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]
            ),
            "fa_notti": st.column_config.CheckboxColumn("Notti?")
        }
    )
    
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    
    if st.button("💾 Salva in Database"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Dati salvati permanentemente!")
    
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(
        pd.DataFrame(columns=["Op A", "Op B"]), 
        num_rows="dynamic", 
        key="inc_editor",
        column_config={
            "Op A": st.column_config.SelectboxColumn("Operatore A", options=lista_nomi),
            "Op B": st.column_config.SelectboxColumn("Operatore B", options=lista_nomi)
        }
    )

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Dal", "Al"]), 
        num_rows="dynamic", 
        key="ass_editor",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)
        }
    )
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(
        pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), 
        num_rows="dynamic", 
        key="pref_editor",
        column_config={
            "Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])
        }
    )

# --- MOTORE DI CALCOLO (CON REGOLA 6 GIORNI) ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    info = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    vinc_map = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in info.items()}
    
    ore_att, notti_att, stato_ciclo, consecutivi = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        is_we = wd >= 5
        occ_oggi = []

        # 1. REGOLA 6 GIORNI
        for n in nomi:
            if consecutivi[n] >= 6:
                res.at[n, col] = "R"; occ_oggi.append(n); consecutivi[n] = 0

        # 2. PREFERENZE
        pref_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in pref_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n)
                ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8)
                consecutivi[n] += 1
                if t == "N": notti_att[n]+=1; stato_ciclo[n]=1

        # 3. CICLO NOTTI AUTOMATICO (Controlla Target 1N)
        notte_occupata = (res[col] == "N").any()
        for n in nomi:
            if n in occ_oggi: continue
            if stato_ciclo[n] == 1:
                if not notte_occupata:
                    res.at[n, col] = "N"; occ_oggi.append(n); ore_att[n]+=9; notti_att[n]+=1; stato_ciclo[n]=2; consecutivi[n]+=1; notte_occupata=True
                else:
                    res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3; consecutivi[n]=0
            elif stato_ciclo[n] in [2, 3]: 
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n] = 3 if stato_ciclo[n]==2 else 0; consecutivi[n]=0

        # 4. RIEMPIMENTO TARGET (2M, 2P, 1N)
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vinc_map.get(n, [])
                    ok = True
                    # Assenze
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    # Regole Notti/Vincoli
                    if t_tipo == "N" and (not info[n]['fa_notti'] or notti_att[n] >= info[n]['max_notti']): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    # Incompatibilità
                    for o in occ_oggi:
                        if res.at[o, col] == t_tipo:
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==o)) | ((inc_df['Op A']==o) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                scelto = min(cand_f, key=lambda x: ore_att[x]/(info[x]['ore']*4) if info[x]['ore']>0 else 1)
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                consecutivi[scelto] += 1
                if t_tipo == "N": notti_att[scelto]+=1; stato_ciclo[scelto]=1

        # Reset consecutivi
        for n in nomi:
            if res.at[n, col] in ["-", " ", "R"]: consecutivi[n] = 0

    return res, ore_att, notti_att

# --- OUTPUT ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_n = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA PIANO V65.1"):
    tab, ore_f, notti_f = genera_piano(anno, mesi.index(m_n) + 1)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura (2-2-1)")
    check_list = []
    for c in tab.columns:
        m, p, n = tab[c].tolist().count("M"), tab[c].tolist().count("P"), tab[c].tolist().count("N")
        check_list.append({"Giorno": c, "M": m, "P": p, "N": n})
    st.table(pd.DataFrame(check_list).set_index("Giorno").T)
    
    st.subheader("📊 Analisi Equità")
    an_data = [{"Operatore": n, "Notti": notti_f[n], "Ore Eff.": ore_f[n], "Target": info[n]['ore']*4, "Sat%": round((ore_f[n]/(info[n]['ore']*4)*100), 1) if info[n]['ore']>0 else 0} for n in tab.index]
    an_df = pd.DataFrame(an_data).set_index("Operatore")
    st.table(an_df)
    st.download_button("📥 Scarica Excel", data=to_excel(tab, an_df), file_name=f"Turni_{m_n}_{anno}.xlsx")
