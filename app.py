import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Turni Smart V64.9", layout="wide", page_icon="🛡️")

DB_FILE = "database_turni_v649.json"

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

# --- INIZIALIZZAZIONE ---
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

st.title("🛡️ Sistema Turni V64.9 - Full Control")

# --- UI GESTIONE ---
with st.expander("⚙️ Configurazione Operatori e Database"):
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic")
    if st.button("💾 Salva in Database"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Dati salvati!")

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic")
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic")

# --- MOTORE DI CALCOLO ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = [o['nome'] for o in st.session_state.operatori]
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    info = {o['nome']: o for o in st.session_state.operatori}
    ore_att, notti_att, stato_ciclo, consecutivi = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}

    for g in range(1, num_g + 1):
        col = cols[g-1]
        is_we = calendar.weekday(anno, mese, g) >= 5
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

        # 3. CICLO NOTTI (CON FIX DOPPIA NOTTE)
        notte_ok = (res[col] == "N").any()
        for n in nomi:
            if n in occ_oggi: continue
            if stato_ciclo[n] == 1:
                if not notte_ok:
                    res.at[n, col] = "N"; occ_oggi.append(n); ore_att[n]+=9; notti_att[n]+=1; stato_ciclo[n]=2; consecutivi[n]+=1; notte_ok=True
                else:
                    res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3; consecutivi[n]=0
            elif stato_ciclo[n] == 2: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3; consecutivi[n]=0
            elif stato_ciclo[n] == 3: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0; consecutivi[n]=0

        # 4. RIEMPIMENTO TARGET 2-2-1
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                # Filtri base
                cand = [n for n in cand if not any(r['Operatore']==n and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows())]
                if t_tipo == "N": cand = [n for n in cand if info[n]['fa_notti'] and notti_att[n] < info[n]['max_notti']]
                
                if not cand: break
                scelto = min(cand, key=lambda x: ore_att[x]/(info[x]['ore']*4) if info[x]['ore']>0 else 1)
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                consecutivi[scelto] += 1
                if t_tipo == "N": notti_att[scelto]+=1; stato_ciclo[scelto]=1

        # Reset consecutivi
        for n in nomi:
            if res.at[n, col] in ["-", " ", "R"]: consecutivi[n] = 0

    return res, ore_att, notti_att

# --- OUTPUT ---
if st.button("🚀 GENERA PIANO V64.9"):
    tab, ore_f, notti_f = genera_piano(datetime.now().year, datetime.now().month)
    st.subheader("📅 Tabellone")
    st.dataframe(tab)
    
    # Analisi Equità
    an_data = []
    for n in tab.index:
        an_data.append({"Operatore": n, "Notti": notti_f[n], "Ore": ore_f[n], "Target": info[n]['ore']*4, "Sat%": (ore_f[n]/(info[n]['ore']*4)*100) if info[n]['ore']>0 else 0})
    an_df = pd.DataFrame(an_data).set_index("Operatore")
    st.subheader("📊 Analisi Equità")
    st.table(an_df)
    
    st.download_button("📥 Excel", data=to_excel(tab, an_df), file_name="turni.xlsx")
