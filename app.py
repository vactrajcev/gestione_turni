import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V66.5 - Full Stats", layout="wide", page_icon="⚖️")

DB_FILE = "database_turni_v66.json"

def carica_dati():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return None
    return None

def salva_dati(operatori):
    with open(DB_FILE, "w") as f: json.dump(operatori, f)

def to_excel(df, analisi_df, copertura_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
        copertura_df.to_excel(writer, sheet_name='Copertura Oraria')
    return output.getvalue()

# --- INIZIALIZZAZIONE ---
if 'operatori' not in st.session_state:
    dati = carica_dati()
    st.session_state.operatori = dati if dati else [
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["Solo Mattina", "No Weekend"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []}
    ]

st.title("⚖️ Sistema Turni V66.5 - Report Completo 2-2-1")

# --- UI GESTIONE ---
with st.expander("⚙️ Squadra & Vincoli"):
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="editor_op")
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    if st.button("💾 Salva Squadra"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Dati salvati!")

    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_ed",
                             column_config={"Op A": st.column_config.SelectboxColumn("Op 1", options=lista_nomi),
                                            "Op B": st.column_config.SelectboxColumn("Op 2", options=lista_nomi)})

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
    nomi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    res = pd.DataFrame("-", index=nomi, columns=cols)
    info_m = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    vinc_m = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in info_m.items()}
    
    ore_att, notti_att, stato_c, cons = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}
    
    # Logica Weekend Protetto
    weekend_list = []
    for g in range(1, num_g):
        if calendar.weekday(anno, mese, g) == 5: weekend_list.append((g, g+1))
    
    we_protetto = {}
    for i, n in enumerate(nomi):
        if "no weekend" in vinc_m.get(n, []): we_protetto[n] = -1
        else: we_protetto[n] = weekend_list[i % len(weekend_list)] if weekend_list else -1

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        col_prev = cols[g-2] if g > 1 else None
        is_we = wd >= 5
        occ_oggi = []

        # 1. SPECIAL RULE: NoWeekend + Solo Mattina (Lun-Ven)
        if not is_we:
            for n in nomi:
                v = vinc_m.get(n, [])
                if "no weekend" in v and "solo mattina" in v:
                    if not any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()):
                        res.at[n, col] = "M"; occ_oggi.append(n); ore_att[n] += 7; cons[n] += 1

        # 2. RIPOSO 6 GIORNI
        for n in nomi:
            if cons[n] >= 6 and n not in occ_oggi:
                res.at[n, col] = " "; occ_oggi.append(n); cons[n] = 0

        # 3. PREFERENZE
        p_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in p_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                if t == "M" and col_prev and res.at[n, col_prev] == "P": continue
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8); cons[n] += 1
                if t == "N": notti_att[n]+=1; stato_c[n]=1

        # 4. CICLO NOTTE (N-N-S-R)
        n_assegnata = (res[col] == "N").any()
        for n in nomi:
            if n in occ_oggi: continue
            if stato_c[n] == 1: # N2
                if not n_assegnata and info_m[n]['fa_notti'] and notti_att[n] < info_m[n]['max_notti']:
                    res.at[n, col] = "N"; occ_oggi.append(n); ore_att[n]+=9; notti_att[n]+=1; stato_c[n]=2; cons[n]+=1; n_assegnata=True
                else: res.at[n, col] = " "; occ_oggi.append(n); stato_c[n] = 3; cons[n] = 0
            elif stato_c[n] == 2: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n] = 3; cons[n] = 0
            elif stato_c[n] == 3: # Riposo
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n] = 0; cons[n] = 0

        # 5. RIEMPIMENTO 2-2-1
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v, ok = vinc_m.get(n, []), True
                    if n in we_protetto and we_protetto[n] != -1 and g in we_protetto[n]: ok = False
                    if t_tipo == "M" and col_prev and res.at[n, col_prev] == "P": ok = False
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    if t_tipo == "N" and (not info_m[n]['fa_notti'] or notti_att[n] >= info_m[n]['max_notti']): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    for gia_in in occ_oggi:
                        if res.at[gia_in, col] == t_tipo:
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==gia_in)) | ((inc_df['Op A']==gia_in) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                scelto = min(cand_f, key=lambda x: (notti_att[x] if t_tipo=="N" else ore_att[x]/(info_m[x]['ore']*4) if info_m[x]['ore']>0 else 1))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8); cons[scelto] += 1
                if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1

        for n in nomi:
            if res.at[n, col] in ["-", " ", "R"]: cons[n] = 0
            
    # Conteggio WE Liberi
    we_liberi = {n: 0 for n in nomi}
    for n in nomi:
        for sab, dom in weekend_list:
            if res.at[n, cols[sab-1]] in ["-", " ", "R"] and res.at[n, cols[dom-1]] in ["-", " ", "R"]:
                we_liberi[n] += 1
                    
    return res, ore_att, notti_att, info_m, we_liberi

# --- VISUALIZZAZIONE ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_sel = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA REPORT COMPLETO V66.5"):
    tab, ore_f, notti_f, info_f, we_f = genera_piano(anno, mesi.index(m_sel) + 1)
    
    st.subheader("📅 Tabellone Turni Mensile")
    st.dataframe(tab, use_container_width=True)
    
    # --- NUOVA TABELLA COPERTURA 2-2-1 ---
    st.subheader("✅ Tabella di Copertura (Standard 2-2-1)")
    cop_list = []
    for c in tab.columns:
        m = tab[c].tolist().count("M")
        p = tab[c].tolist().count("P")
        n = tab[c].tolist().count("N")
        ore_tot = (m*7) + (p*8) + (n*9)
        cop_list.append({"Giorno": c, "M (Target 2)": m, "P (Target 2)": p, "N (Target 1)": n, "Ore Totali": ore_tot})
    
    cop_df = pd.DataFrame(cop_list).set_index("Giorno").T
    st.table(cop_df)
    
    # --- TABELLA ANALISI CON TOTALI ---
    st.subheader("📊 Analisi Squadra ed Equità")
    an_data = [{"Operatore": n, "Notti": notti_f[n], "WE Liberi": we_f[n], "Ore Eff.": ore_f[n], "Target Mensile": info_f[n]['ore']*4, "Sat%": round((ore_f[n]/(info_f[n]['ore']*4)*100), 1) if info_f[n]['ore']>0 else 0} for n in tab.index]
    an_df = pd.DataFrame(an_data)
    
    # Riga Totali
    totali = pd.DataFrame({
        "Operatore": ["TOTALI SQUADRA"],
        "Notti": [an_df["Notti"].sum()],
        "WE Liberi": [an_df["WE Liberi"].sum()],
        "Ore Eff.": [an_df["Ore Eff."].sum()],
        "Target Mensile": [an_df["Target Mensile"].sum()],
        "Sat%": [round((an_df["Ore Eff."].sum() / an_df["Target Mensile"].sum() * 100), 1) if an_df["Target Mensile"].sum() > 0 else 0]
    })
    
    final_analysis = pd.concat([an_df, totali], ignore_index=True).set_index("Operatore")
    st.table(final_analysis)
    
    st.download_button("📥 Scarica Report Excel Completo", 
                       data=to_excel(tab, final_analysis, cop_df), 
                       file_name=f"Turni_Completi_{m_sel}_{anno}.xlsx")
