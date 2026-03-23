import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V44", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V44")
st.markdown("### 🏆 Versione Full: Regole V40 + Protezione Riposo Notte")

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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v44",
                           column_config={
                               "fa_notti": st.column_config.CheckboxColumn("Notti?"),
                               "max_notti": st.column_config.NumberColumn("Max N"),
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"])
                           }, use_container_width=True)
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità (Regola V40)")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v44",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v44",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v44",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- FUNZIONI DI CONTROLLO ---
def check_inc(nome, occupati, df_inc):
    if df_inc.empty: return True
    for o in occupati:
        if not df_inc[((df_inc['Op A']==nome) & (df_inc['Op B']==o)) | ((df_inc['Op A']==o) & (df_inc['Op B']==nome))].empty: return False
    return True

def get_vietati(nome, df_ass):
    v = set()
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            start = int(r['Dal'])
            end = int(r['Al']) if pd.notna(r['Al']) else start
            for g in range(start, end + 1): v.add(g)
    return v

# --- GENERAZIONE ---
def genera_v44(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    
    ha_fatto_notte_ieri = {n: False for n in nomi}

    for g_idx, col in enumerate(cols):
        g = g_idx + 1
        is_we = calendar.weekday(anno, mese, g) >= 5
        occ_oggi = []

        # REGOLA: Chi ha fatto notte ieri oggi è in RIPOSO (R)
        for n in nomi:
            if ha_fatto_notte_ieri[n]:
                res.at[n, col] = "R"
                occ_oggi.append(n)
                ha_fatto_notte_ieri[n] = False 

        # 1. Preferenze
        for _, p in pref_df[pref_df['Giorno'] == g].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi and g not in get_vietati(n, ass_df):
                if check_inc(n, occ_oggi, inc_df):
                    res.at[n, col] = t
                    occ_oggi.append(n)
                    ore[n] += (9 if t=="N" else 7 if t=="M" else 8)
                    if t == "N": 
                        notti[n] += 1
                        ha_fatto_notte_ieri[n] = True

        # 2. Auto (N, M, P) - Logica 2-2-1
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi and g not in get_vietati(n, ass_df)]
                cand = [n for n in cand if check_inc(n, occ_oggi, inc_df)]
                
                # Controllo Notti e Vincoli
                cand_filtrati = []
                for n in cand:
                    vinc = op_df.loc[op_df['nome']==n, 'vincoli'].values[0]
                    vinc = [v.lower() for v in vinc] if isinstance(vinc, list) else []
                    
                    ok = True
                    if t_tipo == "N":
                        if not op_df.loc[op_df['nome']==n, 'fa_notti'].values[0] or notti[n] >= lim_n[n]: ok = False
                    if is_we and "no weekend" in vinc: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in vinc or "no mattina" in vinc): ok = False
                    if t_tipo == "P" and ("solo mattina" in vinc or "no pomeriggio" in vinc): ok = False
                    
                    if ok: cand_filtrati.append(n)
                
                if not cand_filtrati: break
                
                # Bilanciamento: Notti basate su conteggio, Diurni su Saturazione %
                scelto = min(cand_filtrati, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x] if targ[x]>0 else 0))
                res.at[scelto, col] = t_tipo
                occ_oggi.append(scelto)
                ore[scelto] += o_val
                if t_tipo == "N":
                    notti[scelto] += 1
                    ha_fatto_notte_ieri[scelto] = True
                    
    return res, ore, targ, notti

# --- OUTPUT ---
if st.button("🚀 GENERA PIANO V44"):
    ris, ore_f, tar_f, not_f = genera_v44(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)

    st.subheader("✅ Verifica Copertura Giornaliera (2-2-1)")
    cop = []
    for c in ris.columns:
        cop.append({"Giorno": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")})
    st.table(pd.DataFrame(cop).set_index("Giorno").T)

    st.subheader("📊 Analisi Equità e Saturazione")
    an = pd.DataFrame({
        "Notti Fatte": [not_f[n] for n in ris.index],
        "Ore Totali": [ore_f[n] for n in ris.index],
        "Target Ore": [tar_f[n] for n in ris.index],
        "Saturazione %": [round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1) for n in ris.index]
    }, index=ris.index)
    st.table(an)
    st.download_button("📥 Scarica Excel", data=to_excel(ris, an), file_name=f"Turni_V44_{mese_scelto_nome}.xlsx")
