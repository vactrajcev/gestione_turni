import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V52", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V52")
st.markdown("### 💎 Versione Completa: Tutti i pezzi V40 + N-N-S-R + Weekend Libero")

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
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v52")
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v52",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v52",
                            column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v52",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- FUNZIONI SUPPORTO ---
def check_inc(nome, occupati, df_inc):
    for o in occupati:
        if not df_inc[((df_inc['Op A']==nome) & (df_inc['Op B']==o)) | ((df_inc['Op A']==o) & (df_inc['Op B']==nome))].empty: return False
    return True

def is_assente(nome, giorno, df_ass):
    for _, r in df_ass.iterrows():
        if r['Operatore'] == nome and pd.notna(r['Dal']):
            if int(r['Dal']) <= giorno <= (int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])): return True
    return False

# --- GENERAZIONE ---
def genera_v52(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    ore, notti = {n: 0 for n in nomi}, {n: 0 for n in nomi}
    targ = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_n = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    
    stato_ciclo = {n: 0 for n in nomi}
    we_lavorati = {n: set() for n in nomi}
    we_totali = 0

    for g in range(1, num_g + 1):
        wd = calendar.weekday(anno, mese, g)
        col = cols[g-1]
        is_we = wd >= 5
        we_id = g // 7
        if wd == 5: we_totali += 1
        occ_oggi = []

        # 1. CICLO NOTTE (N-N-S-R)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); ore[n]+=9; notti[n]+=1; stato_ciclo[n]=2
                if is_we: we_lavorati[n].add(we_id)
            elif stato_ciclo[n] == 2: # SMONTO
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3
            elif stato_ciclo[n] == 3: # RIPOSO
                res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0

        # 2. PREFERENZE
        for _, p in pref_df[pref_df['Giorno'] == g].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi and not is_assente(n, g, ass_df):
                if t == "N" and (not puo_n[n] or notti[n] >= lim_n[n]): continue
                if check_inc(n, occ_oggi, inc_df):
                    res.at[n, col] = t; occ_oggi.append(n); ore[n] += (9 if t=="N" else 7 if t=="M" else 8)
                    if t == "N": {notti.update({n: notti[n]+1}), stato_ciclo.update({n: 1})}
                    if is_we: we_lavorati[n].add(we_id)

        # 3. AUTO (M, P, N)
        for t_tipo, o_val, qta in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi and not is_assente(n, g, ass_df) and check_inc(n, occ_oggi, inc_df)]
                cand_f = []
                for n in cand:
                    v = [i.lower() for i in op_df.loc[op_df['nome']==n, 'vincoli'].values[0]] if isinstance(op_df.loc[op_df['nome']==n, 'vincoli'].values[0], list) else []
                    ok = True
                    if t_tipo == "N" and (not puo_n[n] or notti[n] >= lim_n[n]): ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    # Regola weekend: se non ha ancora weekend liberi, prova a stare libero (tranne se mancano persone)
                    if is_we and len(we_lavorati[n]) >= (we_totali - 1) and len(cand) > qta: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: 
                    cand_f = [n for n in cand if (t_tipo != "N" or (puo_n[n] and notti[n] < lim_n[n]))]
                    if not cand_f: break
                
                scelto = min(cand_f, key=lambda x: (notti[x] if t_tipo=="N" else ore[x]/targ[x] if targ[x]>0 else 0))
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto); ore[scelto] += o_val
                if is_we: we_lavorati[scelto].add(we_id)
                if t_tipo == "N": {notti.update({scelto: notti[scelto]+1}), stato_ciclo.update({scelto: 1})}

    return res, ore, targ, notti, we_lavorati, we_totali

# --- UI ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
mese_scelto_nome = st.sidebar.selectbox("Mese", mesi_ita, index=datetime.now().month - 1)
anno_scelto = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)
mese_scelto_num = mesi_ita.index(mese_scelto_nome) + 1

if st.button("🚀 GENERA PIANO V52"):
    ris, ore_f, tar_f, not_f, we_f, we_t = genera_v52(anno_scelto, mese_scelto_num)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(ris, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura (2-2-1)")
    cop = pd.DataFrame([{"G": c, "M": ris[c].tolist().count("M"), "P": ris[c].tolist().count("P"), "N": ris[c].tolist().count("N")} for c in ris.columns]).set_index("G").T
    st.table(cop)
    
    st.subheader("📊 Analisi Finale")
    an = pd.DataFrame({
        "Notti": [not_f[n] for n in ris.index],
        "Ore Eff.": [ore_f[n] for n in ris.index],
        "Ore Target": [tar_f[n] for n in ris.index],
        "Sat %": [round((ore_f[n]/tar_f[n]*100) if tar_f[n]>0 else 0, 1) for n in ris.index],
        "WE Libero": ["X" if len(we_f[n]) < we_t else "" for n in ris.index]
    }, index=ris.index)
    st.table(an)
    st.download_button("📥 Excel", data=to_excel(ris, an), file_name="Turni_V52.xlsx")
