import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V64.3 - Full Totals", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V64.3")
st.markdown("### 📊 Report Completo: Totali Giornalieri + Totali di Squadra")

def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- 1. DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []}
    ]

# --- 2. INPUT ---
col_op, col_inc = st.columns([1.5, 1])
with col_op:
    st.subheader("👥 Operatori e Vincoli")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v64_3",
                           column_config={
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]),
                               "fa_notti": st.column_config.CheckboxColumn("Notti?")
                           })
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v64_3",
                            column_config={
                                "Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)
                            })

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v64_3",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v64_3",
                             column_config={
                                 "Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                 "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])
                             })

# --- 3. MOTORE V64.3 ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    targ_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_n = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vinc_map = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    ore_att, notti_att, stato_ciclo = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        is_we = wd >= 5
        occ_oggi = []

        # A. NOTTE 2 (Automatico)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); notti_att[n]+=1; ore_att[n]+=9; stato_ciclo[n]=2
            elif stato_ciclo[n] == 2: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3
            elif stato_ciclo[n] == 3: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0

        # B. PREFERENZE
        for _, p in pref_df[pref_df['Giorno'].astype(str) == str(g)].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8)
                if t == "N": notti_att[n]+=1; stato_ciclo[n]=1

        # C. ASSEGNAZIONE
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vinc_map.get(n, [])
                    ok = True
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    if t_tipo == "N" and (not puo_n[n] or notti_att[n] >= lim_n[n]): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    for o in occ_oggi:
                        if res.at[o, col] == t_tipo:
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==o)) | ((inc_df['Op A']==o) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f and t_tipo == "N":
                    cand_f = [n for n in nomi if n not in occ_oggi and puo_n[n] and notti_att[n] < lim_n[n]]
                
                if not cand_f: break
                
                def get_prio(nome):
                    sat = ore_att[nome] / targ_ore[nome] if targ_ore[nome] > 0 else 1
                    ha_rivali = not inc_df[(inc_df['Op A'] == nome) | (inc_df['Op B'] == nome)].empty
                    return sat - (0.05 if ha_rivali else 0)

                if t_tipo == "N":
                    scelto = min(cand_f, key=lambda x: (notti_att[x]/lim_n[x] if lim_n[x]>0 else 1, get_prio(x)))
                    notti_att[scelto] += 1; stato_ciclo[scelto] = 1
                else:
                    scelto = min(cand_f, key=get_prio)
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)

    # Analisi Finale con Totali
    an_rows = []
    for n in nomi:
        r = res.loc[n].tolist()
        n_c, m_c, p_c = r.count("N"), r.count("M"), r.count("P")
        o_e = (n_c*9) + (m_c*7) + (p_c*8)
        an_rows.append({"Operatore": n, "Notti": n_c, "Max": lim_n[n], "Ore Eff.": o_e, "Target": targ_ore[n], "Sat%": round(o_e/targ_ore[n]*100, 1) if targ_ore[n]>0 else 0})
    
    an_df = pd.DataFrame(an_rows)
    totali_riga = pd.DataFrame([{
        "Operatore": "TOTALI", 
        "Notti": an_df["Notti"].sum(), 
        "Max": an_df["Max"].sum(), 
        "Ore Eff.": an_df["Ore Eff."].sum(), 
        "Target": an_df["Target"].sum(), 
        "Sat%": round(an_df["Ore Eff."].sum() / an_df["Target"].sum() * 100, 1) if an_df["Target"].sum() > 0 else 0
    }])
    an_df = pd.concat([an_df, totali_riga], ignore_index=True).set_index("Operatore")
    
    return res, an_df

# --- 4. OUTPUT ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_n = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, value=2026)

if st.button("🚀 GENERA PIANO V64.3"):
    tab, an = genera_piano(anno, mesi.index(m_n) + 1)
    st.subheader("📅 Tabellone")
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura e Ore Giornaliere")
    check_list = []
    for c in tab.columns:
        m, p, n = tab[c].tolist().count("M"), tab[c].tolist().count("P"), tab[c].tolist().count("N")
        ore_tot = (m*7) + (p*8) + (n*9)
        check_list.append({"Giorno": c, "M": m, "P": p, "N": n, "Ore Totali": ore_tot})
    
    st.table(pd.DataFrame(check_list).set_index("Giorno").T)
    
    st.subheader("📊 Analisi Squadra (con Totali)")
    st.table(an)
    st.download_button("📥 Scarica Excel", data=to_excel(tab, an), file_name=f"Turni_V64_3.xlsx")
