import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V56", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V56")
st.markdown("### ⚖️ Bilanciamento Equo Notti e Rispetto Limiti Massimi")

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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v56")
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v56")

# --- LOGICA DI GENERAZIONE ---
def genera_v56(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    # Parametri operatore
    targhetta_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    limiti_notti = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    abilitati_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vincoli_mappa = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    # Contatori in tempo reale per bilanciamento
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

        # 1. CICLO NOTTE (Prosecuzione N-N-S-R)
        for n in nomi:
            if stato_ciclo[n] == 1: # Deve fare la seconda notte
                # Verifichiamo se può fare la seconda notte (limite max)
                if notti_attuali[n] < limiti_notti[n]:
                    res.at[n, col] = "N"; occ_oggi.append(n); notti_attuali[n] += 1; stato_ciclo[n]=2
                    if is_we: we_lavorati[n].add(we_id)
                else:
                    res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=2 # Salta la 2a notte se al limite
            elif stato_ciclo[n] == 2: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3
            elif stato_ciclo[n] == 3: # Riposo
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0

        # 2. ASSEGNAZIONE NUOVI TURNI (Target 2-2-1)
        # Priorità alla Notte (N) per bilanciare meglio
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vincoli_mappa.get(n, [])
                    ok = True
                    # Controlli Rigidi
                    if t_tipo == "N":
                        if not abilitati_notti[n] or notti_attuali[n] >= limiti_notti[n]: ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # CRITERIO DI SCELTA EQUA
                if t_tipo == "N":
                    # Sceglie chi ha fatto meno notti finora
                    scelto = min(cand_f, key=lambda x: notti_attuali[x])
                else:
                    # Sceglie chi ha la saturazione oraria più bassa
                    scelto = min(cand_f, key=lambda x: (ore_attuali[x]/targhetta_ore[x] if targhetta_ore[x]>0 else 0))
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                if t_tipo == "N":
                    notti_attuali[scelto] += 1
                    stato_ciclo[scelto] = 1
                    ore_attuali[scelto] += 9
                elif t_tipo == "M": ore_attuali[scelto] += 7
                elif t_tipo == "P": ore_attuali[scelto] += 8
                
                if is_we: we_lavorati[scelto].add(we_id)

    # --- RICALCOLO ANALISI FINALE ---
    analisi_rows = []
    for n in nomi:
        riga = res.loc[n].tolist()
        n_count = riga.count("N")
        m_count = riga.count("M")
        p_count = riga.count("P")
        ore_eff = (n_count * 9) + (m_count * 7) + (p_count * 8)
        sat = (ore_eff / targhetta_ore[n] * 100) if targhetta_ore[n] > 0 else 0
        we_libero = "X" if len(we_lavorati[n]) < num_we_tot else ""
        
        analisi_rows.append({
            "Operatore": n, "Notti": n_count, "Max Notti": limiti_notti[n], 
            "Ore Eff.": ore_eff, "Ore Target": targhetta_ore[n], 
            "Saturazione %": round(sat, 1), "WE Libero": we_libero
        })

    return res, pd.DataFrame(analisi_rows).set_index("Operatore")

# --- UI ---
mese_nome = st.sidebar.selectbox("Mese", ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"], index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_num = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"].index(mese_nome) + 1

if st.button("🚀 GENERA PIANO V56"):
    tab, an = genera_v56(anno, mese_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab, use_container_width=True)
    st.subheader("📊 Analisi Finale (Bilanciata)")
    st.table(an)
    st.download_button("📥 Excel", data=to_excel(tab, an), file_name=f"Turni_{mese_nome}_V56.xlsx")
