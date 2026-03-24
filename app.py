import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V63", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V63")
st.markdown("### 🧠 Smart Incompatibility Fix (No Touch Notti)")

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

# --- UI INPUT ---
col_op, col_inc = st.columns([1.5, 1])
with col_op:
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v63")
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v63")

# --- MOTORE DI GENERAZIONE V63 ---
def genera_v63(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    targ_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_n = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vinc_map = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    ore_att, notti_att, stato_ciclo = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}
    we_lav = {n: set() for n in nomi}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        is_we, we_id = wd >= 5, g // 7
        occ_oggi = []

        # 1. CICLO NOTTE (Invariato per mantenere equità)
        for n in nomi:
            if stato_ciclo[n] == 1:
                res.at[n, col] = "N"; occ_oggi.append(n); notti_att[n]+=1; ore_att[n]+=9; stato_ciclo[n]=2
                if is_we: we_lav[n].add(we_id)
            elif stato_ciclo[n] == 2: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3
            elif stato_ciclo[n] == 3: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0

        # 2. ASSEGNAZIONE TURNI (N:1, M:2, P:2)
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                
                for n in cand:
                    v = vinc_map.get(n, [])
                    ok = True
                    # Check Vincoli standard (Assenze, Notti, Orari)
                    if t_tipo == "N":
                        if not puo_n[n] or notti_att[n] >= lim_n[n]: ok = False
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    
                    # --- FIX INCOMPATIBILITÀ ---
                    # L'incompatibilità non scarta l'operatore dal GIORNO, ma dal TURNO specifico
                    # Se Op B è già in turno M, Op A non può fare M, ma può ancora fare P o N
                    for o in occ_oggi:
                        if res.at[o, col] == t_tipo: # Controllo solo se l'incompatibile è NELLO STESSO TURNO
                            if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==o)) | ((inc_df['Op A']==o) & (inc_df['Op B']==n))].empty:
                                ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # Criterio di scelta: Bilanciamento (Notti per N, Ore per M/P)
                if t_tipo == "N":
                    scelto = min(cand_f, key=lambda x: (notti_att[x], ore_att[x]/targ_ore[x]))
                    notti_att[scelto] += 1
                    stato_ciclo[scelto] = 1
                else:
                    scelto = min(cand_f, key=lambda x: (ore_att[x]/targ_ore[x] if targ_ore[x]>0 else 99))
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                if is_we: we_lav[scelto].add(we_id)

    # Analisi finale
    an_rows = []
    for n in nomi:
        r = res.loc[n].tolist()
        n_c, m_c, p_c = r.count("N"), r.count("M"), r.count("P")
        o_e = (n_c*9) + (m_c*7) + (p_c*8)
        an_rows.append({"Operatore": n, "Notti": n_c, "Ore Eff.": o_e, "Target": targ_ore[n], "Sat%": round(o_e/targ_ore[n]*100, 1) if targ_ore[n]>0 else 0})
    
    return res, pd.DataFrame(an_rows).set_index("Operatore")

# --- UI ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_n = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)

if st.button("🚀 GENERA PIANO V63"):
    tab, an = genera_v63(anno, mesi.index(m_n) + 1)
    st.subheader("📅 Tabellone")
    st.dataframe(tab, use_container_width=True)
    st.subheader("📊 Analisi Finale")
    st.table(an)
    st.download_button("📥 Scarica", data=to_excel(tab, an), file_name="Turni_V63.xlsx")
