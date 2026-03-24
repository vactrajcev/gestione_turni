import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V66.2 - Smart Weekend", layout="wide", page_icon="⚖️")

DB_FILE = "database_turni_v66.json"

def carica_dati():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return None
    return None

def salva_dati(operatori):
    with open(DB_FILE, "w") as f: json.dump(operatori, f)

def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- INIZIALIZZAZIONE ---
if 'operatori' not in st.session_state:
    dati = carica_dati()
    st.session_state.operatori = dati if dati else [
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["Solo Mattina", "No Weekend"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []}
    ]

st.title("⚖️ Sistema Turni V66.2 - Smart Weekend & No P->M")

# --- UI GESTIONE ---
with st.expander("⚙️ Configurazione Squadra"):
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="editor_op",
                             column_config={"vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]),
                                            "fa_notti": st.column_config.CheckboxColumn("Notti?")})
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    if st.button("💾 Salva Database"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Dati salvati!")

    st.subheader("🤝 Coppie Incompatibili")
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
    we_lavorati = {n: 0 for n in nomi} # Contatore weekend impegnati

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        col_prev = cols[g-2] if g > 1 else None
        is_we = wd >= 5
        occ_oggi = []

        # 1. REGOLA NoWeekEnd + Solo Mattina (Lavora Lun-Ven)
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

        # 3. PREFERENZE (con check P->M)
        p_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in p_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                if t == "M" and col_prev and res.at[n, col_prev] == "P": continue
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8); cons[n] += 1
                if t == "N": notti_att[n]+=1; stato_c[n]=1
                if is_we: we_lavorati[n] += 1

        # 4. CICLO NOTTE (N-N-S-R)
        n_assegnata = (res[col] == "N").any()
        for n in nomi:
            if n in occ_oggi: continue
            if stato_c[n] == 1: # N2
                if not n_assegnata and info_m[n]['fa_notti'] and notti_att[n] < info_m[n]['max_notti']:
                    res.at[n, col] = "N"; occ_oggi.append(n); ore_att[n]+=9; notti_att[n]+=1; stato_c[n]=2; cons[n]+=1; n_assegnata=True
                    if is_we: we_lavorati[n] += 1
                else: res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=3; cons[n]=0
            elif stato_c[n] == 2: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=3; cons[n]=0
            elif stato_c[n] == 3: # Riposo
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=0; cons[n]=0

        # 5. RIEMPIMENTO SMART (Incompatibilità + P->M + Weekend Fair)
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v, ok = vinc_m.get(n, []), True
                    if t_tipo == "M" and col_prev and res.at[n, col_prev] == "P": ok = False
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    if t_tipo == "N" and (not info_m[n]['fa_notti'] or notti_att[n] >= info_m[n]['max_notti']): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    
                    # Check Incompatibilità
                    for gia_in in occ_oggi:
                        if res.at[gia_in, col] == t_tipo:
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==gia_in)) | ((inc_df['Op A']==gia_in) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # PRIORITÀ: Se è weekend, scegli chi ha lavorato meno weekend finora
                if is_we:
                    scelto = min(cand_f, key=lambda x: (we_lavorati[x], notti_att[x] if t_tipo=="N" else ore_att[x]))
                    we_lavorati[scelto] += 1
                else:
                    scelto = min(cand_f, key=lambda x: (notti_att[x] if t_tipo=="N" else ore_att[x]/(info_m[x]['ore']*4) if info_m[x]['ore']>0 else 1))
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                cons[scelto] += 1
                if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1

        for n in nomi:
            if res.at[n, col] in ["-", " ", "R"]: cons[n] = 0
    return res, ore_att, notti_att, info_m

# --- VISUALIZZAZIONE ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_sel = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA PIANO V66.2"):
    tab, ore_f, notti_f, info_final = genera_piano(anno, mesi.index(m_sel) + 1)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura Mensile")
    c_list = [{"G": c, "M": tab[c].tolist().count("M"), "P": tab[c].tolist().count("P"), "N": tab[c].tolist().count("N"), "Ore": (tab[c].tolist().count("M")*7)+(tab[c].tolist().count("P")*8)+(tab[c].tolist().count("N")*9)} for c in tab.columns]
    c_df = pd.DataFrame(c_list).set_index("G").T
    c_df["TOTALE MESE"] = c_df.sum(axis=1)
    st.table(c_df)
    
    st.subheader("📊 Analisi Squadra & Equità")
    an_data = [{"Operatore": n, "Notti": notti_f[n], "Max": info_final[n]['max_notti'], "Ore Eff.": ore_f[n], "Target": info_final[n]['ore']*4, "Sat%": round((ore_f[n]/(info_final[n]['ore']*4)*100), 1) if info_final[n]['ore']>0 else 0} for n in tab.index]
    an_df = pd.DataFrame(an_data).set_index("Operatore")
    st.table(pd.concat([an_df, pd.DataFrame({"Notti": [an_df["Notti"].sum()], "Max": [an_df["Max"].sum()], "Ore Eff.": [an_df["Ore Eff."].sum()], "Target": [an_df["Target"].sum()], "Sat%": [0]}, index=["TOTALI"])]))
    st.download_button("📥 Excel", data=to_excel(tab, an_df), file_name=f"Turni_{m_sel}.xlsx")
