import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V49", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V49")
st.markdown("### 🛡️ Fix Notti, Tabella 2-2-1 e Weekend Libero")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- 1. DATABASE OPERATORI ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 6, "vincoli": ["No Pomeriggio"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": True, "max_notti": 10, "vincoli": []}
    ]

# --- 2. INPUT DATI ---
col_op, col_inc = st.columns([1.5, 1])
with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v49",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v49",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v49")
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v49")

# --- GENERAZIONE ---
def genera_v49(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_fare_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    
    stato_ciclo = {n: 0 for n in nomi}
    we_lavorati = {n: set() for n in nomi}

    for g_idx, col in enumerate(cols):
        g = g_idx + 1
        wd = calendar.weekday(anno, mese, g)
        is_we = wd >= 5
        we_idx = (g + 2) // 7 # Approssimativo per il weekend corrente
        occ_oggi = []

        # 1. Ciclo Notti (N-N-S-R) - Visualizzazione Vuota per S/R
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); ore[n] += 9; notti[n] += 1; stato_ciclo[n] = 2
                if is_we: we_lavorati[n].add(we_idx)
            elif stato_ciclo[n] == 2: # SMONTO
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n] = 3
            elif stato_ciclo[n] == 3: # RIPOSO
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n] = 0

        # 2. Preferenze
        for _, p in pref_df[pref_df['Giorno'] == g].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                # Controllo se può fare la notte se la preferenza è N
                if t == "N" and not puo_fare_notti[n]: continue
                res.at[n, col] = t; occ_oggi.append(n)
                ore[n] += (9 if t=="N" else 7 if t=="M" else 8)
                if t == "N": {notti.update({n: notti[n]+1}), stato_ciclo.update({n: 1})}
                if is_we: we_lavorati[n].add(we_idx)

        # 3. Auto (Target 2-2-1)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_filtrati = []
                for n in cand:
                    vinc = op_df.loc[op_df['nome']==n, 'vincoli'].values[0]
                    vinc = [v.lower() for v in vinc] if isinstance(vinc, list) else []
                    ok = True
                    
                    # BLOCCO NOTTI RIGIDO
                    if t_tipo == "N":
                        if not puo_fare_notti[n] or notti[n] >= lim_n[n]: ok = False
                    
                    # Weekend Libero (almeno uno al mese)
                    if is_we and len(we_lavorati[n]) >= 2: ok = False
                    
                    # Vincoli Orari
                    if is_we and "no weekend" in vinc: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in vinc or "no mattina" in vinc): ok = False
                    if t_tipo == "P" and ("solo mattina" in vinc or "no pomeriggio" in vinc): ok = False
                    
                    if ok: cand_filtrati.append(n)
                
                if not cand_filtrati: # Allenta solo weekend libero, mai il blocco notti
                    cand_filtrati = [n for n in cand if (t_tipo != "N" or (puo_fare_notti[n] and notti[n] < lim_n[n]))]
                    if not cand_filtrati: break
                
                scelto = min(cand_filtrati, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x] if targ[x]>0 else 0))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto); ore[scelto] += o_val
                if is_we: we_lavorati[scelto].add(we_idx)
                if t_tipo == "N": {notti.update({scelto: notti[scelto]+1}), stato_ciclo.update({scelto: 1})}
                    
    return res, ore, targ, notti

# --- OUTPUT ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

if st.button("🚀 GENERA PIANO V49"):
    ris, ore_f, tar_f, not_f = genera_v49(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura Giornaliera (2-2-1)")
    cop = []
    for c in ris.columns:
        cop.append({"Giorno": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(cop).set_index("Giorno").T)
    
    st.subheader("📊 Analisi Ore e Notti")
    an = pd.DataFrame({
        "Notti": [not_f[n] for n in ris.index],
        "Ore Effettive": [ore_f[n] for n in ris.index],
        "Ore Target": [tar_f[n] for n in ris.index],
        "Sat %": [round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1) for n in ris.index]
    }, index=ris.index)
    st.table(an)
    st.download_button("📥 Excel", data=to_excel(ris, an), file_name="Turni_V49.xlsx")
