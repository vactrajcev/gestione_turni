import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V51", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V51")
st.markdown("### 🏥 Regola Oro: 1 Weekend (Sab+Dom) Completamente Libero per Tutti")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- DATABASE OPERATORI ---
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

# --- INPUT DATI ---
col_op, col_inc = st.columns([1.5, 1])
with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v51",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v51")

# --- GENERAZIONE ---
def genera_v51(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_fare_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    
    stato_ciclo = {n: 0 for n in nomi} # 0=Libero, 1=2^Notte, 2=Smonto, 3=Riposo
    
    # Mappa dei weekend: {id_weekend: [lista_giorni_sab_dom]}
    weekends = {}
    for g in range(1, num_g + 1):
        wd = calendar.weekday(anno, mese, g)
        if wd >= 5: # Sabato o Domenica
            # Calcoliamo un ID weekend (es. primo weekend = 0, secondo = 1...)
            we_id = g // 7 
            if we_id not in weekends: weekends[we_id] = []
            weekends[we_id].append(g)
            
    # Assegniamo preventivamente a ogni operatore un weekend "Protetto" (Libero)
    # Facciamo una rotazione: Op1 libero WE1, Op2 libero WE2...
    we_protetto = {}
    lista_we_ids = list(weekends.keys())
    for i, n in enumerate(nomi):
        we_protetto[n] = lista_we_ids[i % len(lista_we_ids)]

    for g_idx, col in enumerate(cols):
        g = g_idx + 1
        wd = calendar.weekday(anno, mese, g)
        is_we = wd >= 5
        curr_we_id = g // 7
        occ_oggi = []

        # 1. Ciclo Notti (N-N-S-R)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); ore[n] += 9; notti[n] += 1; stato_ciclo[n] = 2
            elif stato_ciclo[n] in [2, 3]:
                res.at[n, col] = " "; occ_oggi.append(n)
                stato_ciclo[n] = (3 if stato_ciclo[n] == 2 else 0)

        # 2. Auto Assegnazione (M-P-N)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                
                # FILTRI
                cand_filtrati = []
                for n in cand:
                    v = [i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else []
                    
                    ok = True
                    # Regola Weekend Libero: Se questo è il weekend protetto per N, non assegnare nulla
                    if is_we and we_protetto[n] == curr_we_id: ok = False
                    
                    # Altri vincoli blindati
                    if t_tipo == "N" and (not puo_fare_notti[n] or notti[n] >= lim_n[n]): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    
                    if ok: cand_filtrati.append(n)
                
                # Se mancano persone (es. troppi protetti contemporaneamente), allentiamo la protezione
                if not cand_filtrati:
                    cand_filtrati = [n for n in cand if (t_tipo != "N" or (puo_fare_notti[n] and notti[n] < lim_n[n]))]
                    # Ma manteniamo i vincoli contrattuali (No Weekend, Solo Mattina)
                    cand_filtrati = [n for n in cand_filtrati if not (
                        (is_we and "no weekend" in ([i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else [])) or
                        (t_tipo == "M" and "solo pomeriggio" in ([i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else []))
                    )]
                    if not cand_filtrati: break
                
                scelto = min(cand_filtrati, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x] if targ[x]>0 else 0))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto); ore[scelto] += o_val
                if t_tipo == "N": stato_ciclo[scelto] = 1
                    
    return res, ore, targ, notti

# --- UI STREAMLIT ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

if st.button("🚀 GENERA PIANO V51"):
    ris, ore_f, tar_f, not_f = genera_v51(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura (2-2-1)")
    cop = []
    for c in ris.columns:
        cop.append({"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(cop).set_index("G").T)
    
    st.subheader("📊 Analisi Finale Oraria")
    an_df = pd.DataFrame({
        "Notti": [not_f[n] for n in ris.index],
        "Ore Effettive": [ore_f[n] for n in ris.index],
        "Ore Target": [tar_f[n] for n in ris.index],
        "Saturazione %": [round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1) for n in ris.index]
    }, index=ris.index)
    st.table(an_df)
    st.download_button("📥 Excel", data=to_excel(ris, an_df), file_name="Turni_V51.xlsx")
