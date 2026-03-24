import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V67.3 - No Buchi", layout="wide", page_icon="⚖️")

DB_FILE = "database_turni_v66.json"

def carica_dati():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return None
    return None

def salva_dati(operatori):
    with open(DB_FILE, "w") as f: json.dump(operatori, f)

def to_excel(tab, an_df, cop_df, gett_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        tab.to_excel(writer, sheet_name='Tabellone')
        an_df.to_excel(writer, sheet_name='Analisi Fissi')
        cop_df.to_excel(writer, sheet_name='Copertura 2-2-1')
        gett_df.to_excel(writer, sheet_name='Gettonisti')
    return output.getvalue()

# --- INIZIALIZZAZIONE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = carica_dati() or []

st.title("⚖️ Sistema Turni V67.3 - Copertura Garantita")

# --- 1. CONFIGURAZIONE SQUADRA FISSA ---
with st.expander("⚙️ 1. Personale Fisso & Incompatibilità"):
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="editor_op",
                             column_config={"vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]),
                                            "fa_notti": st.column_config.CheckboxColumn("Notti?")})
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    
    if st.button("💾 Salva Dipendenti"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Database Fissi Aggiornato!")

    st.subheader("🤝 Coppie Incompatibili")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_ed",
                             column_config={"Op A": st.column_config.SelectboxColumn("Op 1", options=lista_nomi),
                                            "Op B": st.column_config.SelectboxColumn("Op 2", options=lista_nomi)})

# --- 2. GETTONISTI ---
with st.expander("🃏 2. Disponibilità Gettonisti"):
    gett_input_df = st.data_editor(
        pd.DataFrame(columns=["Nome Gettonista", "Giorno", "Preferenza Turno"]), 
        num_rows="dynamic",
        key="gett_ed",
        column_config={
            "Preferenza Turno": st.column_config.SelectboxColumn("Turno", options=["Qualsiasi", "M", "P", "N"]),
            "Giorno": st.column_config.NumberColumn("Giorno", min_value=1, max_value=31)
        }
    )

# --- 3. ASSENZE E PREFERENZE ---
col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze Fissi")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze Fissi")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- MOTORE DI CALCOLO V67.3 ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi_fissi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    
    res = pd.DataFrame("-", index=nomi_fissi, columns=cols)
    info_m = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    vinc_m = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in info_m.items()}
    
    ore_att, notti_att, stato_c, cons = {n: 0 for n in nomi_fissi}, {n: 0 for n in nomi_fissi}, {n: 0 for n in nomi_fissi}, {n: 0 for n in nomi_fissi}
    
    weekend_list = []
    for g in range(1, num_g + 1):
        if calendar.weekday(anno, mese, g) == 5:
            if g + 1 <= num_g: weekend_list.append((g, g+1))
    
    we_protetto = {n: (weekend_list[i % len(weekend_list)] if weekend_list else -1) for i, n in enumerate(nomi_fissi)}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        col_prev = cols[g-2] if g > 1 else None
        is_we, occ_oggi = wd >= 5, []

        # 1. Preferenze e Assenze (Priorità assoluta)
        p_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in p_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi_fissi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8); cons[n] += 1
                if t == "N": notti_att[n]+=1; stato_c[n]=1

        # 2. Ciclo Notte Fissi
        n_assegnata = (res[col] == "N").any()
        for n in nomi_fissi:
            if n in occ_oggi: continue
            if stato_c[n] == 1: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=2; cons[n]=0
            elif stato_c[n] == 2: # Riposo post-notte
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=0; cons[n]=0

        # 3. Riempimento 2-2-1 con Gerarchia di Emergenza
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                # LIVELLO A: Fissi liberi (No vincoli, No we_protetto)
                cand = [n for n in nomi_fissi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v, ok = vinc_m.get(n, []), True
                    if n in we_protetto and we_protetto[n] != -1 and g in we_protetto[n]: ok = False
                    if t_tipo == "M" and col_prev and res.at[n, col_prev] == "P": ok = False
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    for gia_in in occ_oggi:
                        if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==gia_in)) | ((inc_df['Op A']==gia_in) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if cand_f:
                    scelto = min(cand_f, key=lambda x: (notti_att[x] if t_tipo=="N" else ore_att[x]))
                    res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                    ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8); cons[scelto] += 1
                    if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1
                    continue

                # LIVELLO B: Gettonisti
                get_disp = gett_input_df[(gett_input_df['Giorno'] == g) & ((gett_input_df['Preferenza Turno'] == t_tipo) | (gett_input_df['Preferenza Turno'] == "Qualsiasi"))]
                valido_get = None
                for _, r_g in get_disp.iterrows():
                    gn = r_g['Nome Gettonista'] + " (GET)"
                    if gn not in occ_oggi: valido_get = gn; break
                
                if valido_get:
                    if valido_get not in res.index: res = pd.concat([res, pd.DataFrame("-", index=[valido_get], columns=res.columns)])
                    res.at[valido_get, col] = t_tipo; occ_oggi.append(valido_get)
                    continue

                # LIVELLO C: Fissi (Ignorando weekend protetto ma non le assenze)
                cand_emergenza = [n for n in nomi_fissi if n not in occ_oggi]
                cand_e_f = []
                for n in cand_emergenza:
                    v, ok = vinc_m.get(n, []), True
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if ok: cand_e_f.append(n)
                
                if cand_e_f:
                    scelto = min(cand_e_f, key=lambda x: ore_att[x])
                    res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                    ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8); cons[scelto] += 1
                else: break 

    # Conteggio Weekend Liberi (Regola 66.9)
    we_liberi = {n: 0 for n in nomi_fissi}
    for n in nomi_fissi:
        for sab_idx, dom_idx in weekend_list:
            if res.at[n, cols[sab_idx-1]] in ["-", " ", "R"] and res.at[n, cols[dom_idx-1]] in ["-", " ", "R"]:
                we_liberi[n] += 1
    return res, ore_att, notti_att, info_m, we_liberi

# --- VISUALIZZAZIONE ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_sel = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA REPORT V67.3"):
    tab, ore_f, notti_f, info_f, we_f = genera_piano(anno, mesi.index(m_sel) + 1)
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Tabella Copertura (2-2-1)")
    cop_list = []
    for c in tab.columns:
        m, p, n = tab[c].tolist().count("M"), tab[c].tolist().count("P"), tab[c].tolist().count("N")
        cop_list.append({"G": c, "M": m, "P": p, "N": n, "Ore": (m*7)+(p*8)+(n*9)})
    cop_df = pd.DataFrame(cop_list).set_index("G").T
    cop_df["TOTALI"] = cop_df.sum(axis=1)
    st.table(cop_df)
    
    st.subheader("📊 Analisi Squadra Fissa")
    an_df = pd.DataFrame([{"Operatore": n, "Notti": notti_f[n], "WE Liberi": we_f[n], "Ore Eff.": ore_f[n], "Target": info_f[n]['ore']*4, "Sat%": round((ore_f[n]/(info_f[n]['ore']*4)*100),1) if info_f[n]['ore']>0 else 0} for n in tab.index if "(GET)" not in n])
    tot_row = pd.DataFrame({"Operatore": ["TOTALI"], "Notti": [an_df["Notti"].sum()], "WE Liberi": [an_df["WE Liberi"].sum()], "Ore Eff.": [an_df["Ore Eff."].sum()], "Target": [an_df["Target"].sum()], "Sat%": [0]})
    st.table(pd.concat([an_df, tot_row], ignore_index=True).set_index("Operatore"))

    st.download_button("📥 Excel", data=to_excel(tab, an_df, cop_df, gett_input_df), file_name=f"Turni_{m_sel}.xlsx")
