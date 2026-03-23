import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V50", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V50")
st.markdown("### 🛡️ Vincoli Blindati + Indicatore Weekend Libero (X)")

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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v50",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v50")

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v50")
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v50")

# --- GENERAZIONE ---
def genera_v50(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_fare_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    
    # Tracking weekend
    stato_ciclo = {n: 0 for n in nomi}
    we_assegnati = {n: set() for n in nomi} # weekend in cui l'operatore lavora
    
    # Identifica i weekend del mese (coppie Sab-Dom)
    weekend_days = []
    for g in range(1, num_g + 1):
        if calendar.weekday(anno, mese, g) >= 5: weekend_days.append(g)

    for g_idx, col in enumerate(cols):
        g = g_idx + 1
        wd = calendar.weekday(anno, mese, g)
        is_we = wd >= 5
        we_id = (g + calendar.monthrange(anno, mese)[0]) // 7
        occ_oggi = []

        # 1. Ciclo Notti (N-N-S-R)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); ore[n] += 9; notti[n] += 1; stato_ciclo[n] = 2
                if is_we: we_assegnati[n].add(we_id)
            elif stato_ciclo[n] == 2 or stato_ciclo[n] == 3:
                res.at[n, col] = " "; occ_oggi.append(n)
                stato_ciclo[n] = (3 if stato_ciclo[n] == 2 else 0)

        # 2. Preferenze
        for _, p in pref_df[pref_df['Giorno'] == g].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n)
                ore[n] += (9 if t=="N" else 7 if t=="M" else 8)
                if t == "N": {notti.update({n: notti[n]+1}), stato_ciclo.update({n: 1})}
                if is_we: we_assegnati[n].add(we_id)

        # 3. Auto (2-2-1)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_filtrati = []
                for n in cand:
                    v = [i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else []
                    
                    # VINCOLI BLINDATI
                    ok = True
                    if t_tipo == "N" and (not puo_fare_notti[n] or notti[n] >= lim_n[n]): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    
                    # Tentativo Weekend Libero (se ha già fatto 2 weekend, proviamo a evitarlo)
                    if is_we and len(we_assegnati[n]) >= 2: ok = False
                    
                    if ok: cand_filtrati.append(n)
                
                if not cand_filtrati:
                    # Se non ci sono candidati con "weekend libero", allentiamo SOLO quella regola, non i vincoli orari
                    cand_filtrati = [n for n in cand if (t_tipo != "N" or (puo_fare_notti[n] and notti[n] < lim_n[n]))]
                    # Riapplica i vincoli orari fondamentali anche nell'allentamento
                    cand_filtrati = [n for n in cand_filtrati if not (
                        (is_we and "no weekend" in ([i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else [])) or
                        (t_tipo == "M" and "solo pomeriggio" in ([i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else []))
                    )]
                    if not cand_filtrati: break
                
                scelto = min(cand_filtrati, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x] if targ[x]>0 else 0))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto); ore[scelto] += o_val
                if is_we: we_assegnati[scelto].add(we_id)
                if t_tipo == "N": {notti.update({scelto: notti[scelto]+1}), stato_ciclo.update({scelto: 1})}
                    
    return res, ore, targ, notti, we_assegnati

# --- OUTPUT ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

if st.button("🚀 GENERA PIANO V50"):
    ris, ore_f, tar_f, not_f, we_f = genera_v50(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura (2-2-1)")
    cop = []
    for c in ris.columns:
        cop.append({"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(cop).set_index("G").T)
    
    st.subheader("📊 Analisi e Weekend Liberi")
    # Calcolo weekend totali nel mese per segnare la X
    num_we_tot = (calendar.monthrange(anno_scelto, mese_scelto_num)[1] + calendar.monthrange(anno_scelto, mese_scelto_num)[0]) // 7
    
    an_data = []
    for n in ris.index:
        we_lavorati = len(we_f[n])
        ha_we_libero = "X" if we_lavorati < num_we_tot else ""
        an_data.append({
            "Operatore": n,
            "Notti": not_f[n],
            "Ore Eff.": ore_f[n],
            "Ore Target": tar_f[n],
            "Sat %": round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1),
            "WE Libero?": ha_we_libero
        })
    st.table(pd.DataFrame(an_data).set_index("Operatore"))
    st.download_button("📥 Excel", data=to_excel(ris, pd.DataFrame(an_data)), file_name="Turni_V50.xlsx")
