import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V42", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V42")
st.markdown("### Verifica Copertura 2-2-1 e Bilanciamento Notti")

# --- FUNZIONE EXCEL ---
def to_excel(df, analisi_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tabella Turni')
        analisi_df.to_excel(writer, sheet_name='Analisi Equità')
    return output.getvalue()

# --- SIDEBAR ---
st.sidebar.header("📅 Periodo")
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v42",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v42",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v42",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v42",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- CONTROLLI ---
def check_inc(nome, occupati, df_inc):
    if df_inc.empty: return True
    for o in occupati:
        if not df_inc[((df_inc['Op A']==nome) & (df_inc['Op B']==o)) | ((df_inc['Op A']==o) & (df_inc['Op B']==nome))].empty: return False
    return True

def get_vietati(nome, df_ass):
    v = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            for g in range(int(r['Dal']), (int(r['Al'])+1 if pd.notna(r['Al']) else int(r['Dal'])+1)): v.add(g)
    return v

def check_vincoli(nome, turno, is_we, df_op):
    r = df_op[df_op['nome'] == nome]
    if r.empty: return True
    if turno == "N" and not r['fa_notti'].values[0]: return False
    v = [i.lower() for i in r['vincoli'].values[0]] if isinstance(r['vincoli'].values[0], list) else []
    if is_we and "no weekend" in v: return False
    if turno == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
    if turno == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
    return True

# --- GENERAZIONE ---
def genera_v42(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    smonto = {n: 0 for n in nomi}

    # Alert Capacità Notti
    tot_n_possibili = sum(lim_n.values())
    if tot_n_possibili < num_g:
        st.warning(f"⚠️ Attenzione: Il limite Max Notti totale ({tot_n_possibili}) è inferiore ai giorni del mese ({num_g}).")

    for g_idx, col in enumerate(cols):
        g = g_idx + 1
        is_we = calendar.weekday(anno, mese, g) >= 5
        occ = []

        # 1. Preferenze
        for _, p in pref_df[pref_df['Giorno'] == g].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ:
                res.at[n, col] = t; occ.append(n); ore[n] += (9 if t=="N" else 7)
                if t=="N": {notti.update({n: notti[n]+1}), smonto.update({n: 1})}

        # 2. Smonto
        for n in nomi:
            if smonto[n] == 1 and n not in occ:
                res.at[n, col] = "N"; notti[n] += 1; ore[n] += 9; occ.append(n); smonto[n] = 0

        # 3. Auto (N, M, P)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ and g not in get_vietati(n, ass_df) and check_vincoli(n, t_tipo, is_we, op_df) and check_inc(n, occ, inc_df)]
                if t_tipo == "N": cand = [n for n in cand if notti[n] < lim_n[n]]
                if not cand: break
                
                # Bilanciamento: per Notti guarda notti fatte, per Diurni guarda saturazione ore
                scelto = min(cand, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x]))
                res.at[scelto, col] = t_tipo; occ.append(scelto); ore[scelto] += o_val
                if t_tipo == "N": {notti.update({scelto: notti[scelto]+1}), smonto.update({scelto: 1})}
    return res, ore, targ, notti

# --- OUTPUT ---
if st.button("🚀 GENERA PIANO V42"):
    ris, ore_f, tar_f, not_f = genera_v42(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)

    st.subheader("✅ Verifica Copertura Giornaliera (Target 2-2-1)")
    copertura = []
    for c in ris.columns:
        copertura.append({"Giorno": c, "M (Mattina)": ris[c].tolist().count("M"), "P (Pomeriggio)": ris[c].tolist().count("P"), "N (Notte)": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(copertura).set_index("Giorno").T)

    st.subheader("📊 Analisi Equità")
    an = pd.DataFrame({"Notti": [not_f[n] for n in ris.index], "Ore": [ore_f[n] for n in ris.index], "Saturazione %": [round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1) for n in ris.index]}, index=ris.index)
    st.table(an)
    st.download_button("📥 Scarica Excel", data=to_excel(ris, an), file_name="Turni_V42.xlsx")
