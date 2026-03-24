import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni", layout="wide", page_icon="⚖️")

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
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []}
    ]

st.title("⚖️ Sistema Turni")

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
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- MOTORE DI CALCOLO ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    res = pd.DataFrame("-", index=nomi, columns=cols)
    info_m = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    vinc_m = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in info_m.items()}
    
    ore_att, notti_att, stato_c, cons = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}
    
    weekend_list = []
    for g in range(1, num_g):
        if calendar.weekday(anno, mese, g) == 5: weekend_list.append((g, g+1))
    we_protetto = {n: (weekend_list[i % len(weekend_list)] if weekend_list else -1) for i, n in enumerate(nomi)}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        col_prev = cols[g-2] if g > 1 else None
        is_we, occ_oggi = wd >= 5, []

        # 1. Regola NoWeekend + Solo Mattina
        if not is_we:
            for n in nomi:
                v = vinc_m.get(n, [])
                if "no weekend" in v and "solo mattina" in v:
                    if not any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()):
                        res.at[n, col] = "M"; occ_oggi.append(n); ore_att[n] += 7; cons[n] += 1

        # 2. Riposo 6 giorni
        for n in nomi:
            if cons[n] >= 6 and n not in occ_oggi:
                res.at[n, col] = " "; occ_oggi.append(n); cons[n] = 0

        # 3. Preferenze
        p_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in p_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8); cons[n] += 1
                if t == "N": notti_att[n]+=1; stato_c[n]=1

        # 4. Ciclo Notte
        n_assegnata = (res[col] == "N").any()
        for n in nomi:
            if n in occ_oggi: continue
            if stato_c[n] == 1:
                if not n_assegnata and info_m[n]['fa_notti'] and notti_att[n] < info_m[n]['max_notti']:
                    res.at[n, col] = "N"; occ_oggi.append(n); ore_att[n]+=9; notti_att[n]+=1; stato_c[n]=2; cons[n]+=1; n_assegnata=True
                else: res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=3; cons[n]=0
            elif stato_c[n] == 2: res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=3; cons[n]=0
            elif stato_c[n] == 3: res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=0; cons[n]=0

        # 5. Riempimento 2-2-1
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
                    if ok: cand_f.append(n)
                
                if not cand_f: # Rilassamento weekend protetto se mancano persone
                    cand_f = [n for n in cand if (not any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows())) and (not (is_we and "no weekend" in vinc_m.get(n, [])))]
                
                if not cand_f: break
                scelto = min(cand_f, key=lambda x: (notti_att[x] if t_tipo=="N" else ore_att[x]/(info_m[x]['ore']*4) if info_m[x]['ore']>0 else 1))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8); cons[scelto] += 1
                if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1

        for n in nomi:
            if res.at[n, col] in ["-", " ", "R"]: cons[n] = 0
            
    # NUOVA LOGICA CONTEGGIO WEEKEND LIBERI
    we_liberi = {n: 0 for n in nomi}
    for n in nomi:
        for sab_idx, dom_idx in weekend_list:
            sab_col = cols[sab_idx-1]
            dom_col = cols[dom_idx-1]
            
            # Caso 1: Sabato e Domenica sono entrambi liberi (Riposo/Smonto)
            is_sab_libero = res.at[n, sab_col] in ["-", " ", "R"]
            is_dom_libero = res.at[n, dom_col] in ["-", " ", "R"]
            
            if is_sab_libero and is_dom_libero:
                we_liberi[n] += 1
                    
    return res, ore_att, notti_att, info_m, we_liberi

# --- VISUALIZZAZIONE ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_sel = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2026, value=2026)

if st.button("🚀 GENERA REPORT"):
    tab, ore_f, notti_f, info_f, we_f = genera_piano(anno, mesi.index(m_sel) + 1)
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Tabella Copertura Mensile (2-2-1)")
    cop_list = []
    for c in tab.columns:
        m, p, n = tab[c].tolist().count("M"), tab[c].tolist().count("P"), tab[c].tolist().count("N")
        cop_list.append({"G": c, "Mattina (M)": m, "Pomeriggio (P)": p, "Notte (N)": n, "Ore Erogate": (m*7)+(p*8)+(n*9)})
    cop_df = pd.DataFrame(cop_list).set_index("G").T
    cop_df["TOTALE MESE"] = cop_df.sum(axis=1)
    st.table(cop_df)
    
    st.subheader("📊 Analisi Squadra ed Equità")
    an_df = pd.DataFrame([{"Operatore": n, "Notti": notti_f[n], "WE Liberi": we_f[n], "Ore Eff.": ore_f[n], "Target": info_f[n]['ore']*4, "Sat%": round((ore_f[n]/(info_f[n]['ore']*4)*100),1) if info_f[n]['ore']>0 else 0} for n in tab.index])
    totali = pd.DataFrame({"Operatore": ["TOTALI"], "Notti": [an_df["Notti"].sum()], "WE Liberi": [an_df["WE Liberi"].sum()], "Ore Eff.": [an_df["Ore Eff."].sum()], "Target": [an_df["Target"].sum()], "Sat%": [0]})
    st.table(pd.concat([an_df, totali], ignore_index=True).set_index("Operatore"))
    st.download_button("📥 Excel", data=to_excel(tab, an_df, cop_df), file_name=f"Turni_{m_sel}.xlsx")
