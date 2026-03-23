import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V54", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V54")
st.markdown("### 🛠️ Fix Analisi: Saturazione Pulita e Conteggio Ore Reale")

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
        {"nome": "NERI ELENA", "ore": 38, "fa_notti": True, "max_notti": 5, "vincoli": ["No Pomeriggio"]},
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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v54")
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v54",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v54",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v54",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- 3. LOGICA DI GENERAZIONE ---
def genera_v54(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore_effettive = {n: 0 for n in nomi}
    notti_fatte = {n: 0 for n in nomi}
    targhetta_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    limiti_notti = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    abilitati_notti = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vincoli_mappa = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    stato_ciclo = {n: 0 for n in nomi}
    # Per il weekend libero, tracciamo i weekend (Sab+Dom) lavorati
    we_lavorati = {n: set() for n in nomi}
    giorni_we = [g for g in range(1, num_g + 1) if calendar.weekday(anno, mese, g) >= 5]
    num_we_tot = len([g for g in giorni_we if calendar.weekday(anno, mese, g) == 5]) # Conta i Sabati

    for g in range(1, num_g + 1):
        wd = calendar.weekday(anno, mese, g)
        col = cols[g-1]
        is_we = wd >= 5
        we_id = (g + calendar.monthrange(anno, mese)[0]) // 7
        occ_oggi = []

        # A. CICLO NOTTE (N-N-S-R)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); ore_effettive[n]+=9; notti_fatte[n]+=1; stato_ciclo[n]=2
                if is_we: we_lavorati[n].add(we_id)
            elif stato_ciclo[n] in [2, 3]:
                res.at[n, col] = " "; occ_oggi.append(n)
                stato_ciclo[n] = (3 if stato_ciclo[n] == 2 else 0)

        # B. ASSEGNAZIONE TURNI (Target 2-2-1)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vincoli_mappa.get(n, [])
                    ok = True
                    # Vincoli Invalicabili
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "N" and (not abilitati_notti[n] or notti_fatte[n] >= limiti_notti[n]): ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    # Assenze
                    if any(r['Operatore'] == n and pd.notna(r['Dal']) and int(r['Dal']) <= g <= (int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    # Incompatibilità
                    for o in occ_oggi:
                        if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==o)) | ((inc_df['Op A']==o) & (inc_df['Op B']==n))].empty: ok = False
                    
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # Scelta per equità (saturazione)
                scelto = min(cand_f, key=lambda x: (notti_fatte[x] if t_tipo=="N" else ore_effettive[x]/targhetta_ore[x] if targhetta_ore[x]>0 else 0))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto); ore_effettive[scelto] += o_val
                if is_we: we_lavorati[scelto].add(we_id)
                if t_tipo == "N": stato_ciclo[scelto] = 1

    return res, ore_effettive, targhetta_ore, notti_fatte, we_lavorati, num_we_tot

# --- 4. INTERFACCIA UTENTE ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

if st.button("🚀 GENERA PIANO V54"):
    ris, ore_f, tar_f, not_f, we_f, we_t = genera_v54(anno_scelto, mese_scelto_num)
    
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura Giornaliera (Target 2-2-1)")
    cop_data = []
    for c in ris.columns:
        cop_data.append({"Giorno": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(cop_data).set_index("Giorno").T)
    
    st.subheader("📊 Analisi Finale")
    an_rows = []
    for n in ris.index:
        sat = (ore_f[n] / tar_f[n] * 100) if tar_f[n] > 0 else 0
        # Ha un weekend libero se i weekend lavorati sono inferiori ai weekend totali del mese
        we_libero = "X" if len(we_f[n]) < we_t else ""
        an_rows.append({
            "Operatore": n,
            "Notti": not_f[n],
            "Ore Eff.": ore_f[n],
            "Ore Target": tar_f[n],
            "Saturazione %": round(sat, 1),
            "WE Libero": we_libero
        })
    
    analisi_df = pd.DataFrame(an_rows).set_index("Operatore")
    st.table(analisi_df)
    
    st.download_button("📥 Scarica in Excel", data=to_excel(ris, analisi_df), file_name=f"Turni_{mese_scelto_nome}_V54.xlsx")
