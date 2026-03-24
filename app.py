import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V57", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V57")
st.markdown("### 🎯 Copertura 2-2-1 e Bilanciamento Notti")

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
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "fa_notti": True, "max_notti": 8, "vincoli": []},
        {"nome": "MISELMI H.", "ore": 38, "fa_notti": True, "max_notti": 8, "vincoli": []},
        {"nome": "SAKLI BESMA", "ore": 38, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "fa_notti": False, "max_notti": 0, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 25, "fa_notti": True, "max_notti": 7, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "fa_notti": True, "max_notti": 7, "vincoli": []}
    ]

# --- INPUT DATI ---
col_op, col_inc = st.columns([1.5, 1])
with col_op:
    st.subheader("👥 Operatori")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v57")
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v57")

# --- LOGICA DI GENERAZIONE ---
def genera_v57(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    targhetta_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    limiti_notti = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    abilitati_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vincoli_mappa = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    notti_attuali = {n: 0 for n in nomi}
    ore_attuali = {n: 0 for n in nomi}
    stato_ciclo = {n: 0 for n in nomi}
    we_lavorati = {n: set() for n in nomi}
    num_we_tot = len([g for g in range(1, num_g + 1) if calendar.weekday(anno, mese, g) == 5])

    for g in range(1, num_g + 1):
        wd = calendar.weekday(anno, mese, g)
        col = cols[g-1]
        is_we = wd >= 5
        we_id = (g + calendar.monthrange(anno, mese)[0]) // 7
        occ_oggi = []

        # 1. GESTIONE CICLO NOTTE ESISTENTE
        for n in nomi:
            if stato_ciclo[n] == 1: # Seconda notte obbligatoria
                res.at[n, col] = "N"; occ_oggi.append(n); notti_attuali[n] += 1; stato_ciclo[n]=2
                if is_we: we_lavorati[n].add(we_id)
            elif stato_ciclo[n] == 2: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3
            elif stato_ciclo[n] == 3: # Riposo
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0

        # 2. ASSEGNAZIONE NUOVI TURNI (Target N:1, M:2, P:2)
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vincoli_mappa.get(n, [])
                    ok = True
                    if t_tipo == "N":
                        if not abilitati_notti[n] or notti_attuali[n] >= limiti_notti[n]: ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no mattina" in v): ok = False # Corretto ref
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # Scelta equa: chi ha meno notti per N, chi ha meno ore per M/P
                if t_tipo == "N":
                    scelto = min(cand_f, key=lambda x: notti_attuali[x])
                    notti_attuali[scelto] += 1
                    stato_ciclo[scelto] = 1
                else:
                    scelto = min(cand_f, key=lambda x: (ore_attuali[x]/targhetta_ore[x] if targhetta_ore[x]>0 else 0))
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_attuali[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                if is_we: we_lavorati[scelto].add(we_id)

    # Preparazione Analisi Finale ricalcolata
    analisi_rows = []
    for n in nomi:
        riga = res.loc[n].tolist()
        n_c, m_c, p_c = riga.count("N"), riga.count("M"), riga.count("P")
        ore_eff = (n_c * 9) + (m_c * 7) + (p_c * 8)
        sat = (ore_eff / targhetta_ore[n] * 100) if targhetta_ore[n] > 0 else 0
        analisi_rows.append({
            "Operatore": n, "Notti": n_c, "Max Notti": limiti_notti[n], 
            "Ore Eff.": ore_eff, "Ore Target": targhetta_ore[n], 
            "Saturazione %": round(sat, 1), "WE Libero": "X" if len(we_lavorati[n]) < num_we_tot else ""
        })

    return res, pd.DataFrame(analisi_rows).set_index("Operatore")

# --- UI ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_nome = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
m_num = mesi.index(m_nome) + 1

if st.button("🚀 GENERA PIANO V57"):
    tab, an = genera_v57(anno, m_num)
    
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab, use_container_width=True)
    
    # --- TABELLA COPERTURA 2-2-1 ---
    st.subheader("✅ Verifica Copertura Giornaliera (Target 2-2-1)")
    check_data = []
    for c in tab.columns:
        check_data.append({
            "Giorno": c, 
            "M": tab[c].tolist().count("M"), 
            "P": tab[c].tolist().count("P"), 
            "N": tab[c].tolist().count("N")
        })
    st.table(pd.DataFrame(check_data).set_index("Giorno").T)
    
    st.subheader("📊 Analisi Finale Bilanciata")
    st.table(an)
    st.download_button("📥 Excel", data=to_excel(tab, an), file_name=f"Turni_{m_nome}_V57.xlsx")
