import streamlit as st
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="Gestione Turni V62 - Balanced", layout="wide")
st.title("🗓️ Sistema Gestione Turni - V62")
st.markdown("### ⚖️ Motore di Distribuzione Equa delle Notti")

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
    st.subheader("👥 Operatori e Vincoli")
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="op_v62",
                           column_config={
                               "vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]),
                               "fa_notti": st.column_config.CheckboxColumn("Notti?")
                           })
    lista_nomi = op_df['nome'].dropna().unique().tolist()

with col_inc:
    st.subheader("🤝 Incompatibilità")
    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_v62",
                            column_config={"Op A": st.column_config.SelectboxColumn("Op A", options=lista_nomi),
                                           "Op B": st.column_config.SelectboxColumn("Op B", options=lista_nomi)})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic", key="ass_v62")
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic", key="pref_v62")

# --- 3. MOTORE DI GENERAZIONE V62 ---
def genera_v62(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi = op_df['nome'].tolist()
    res = pd.DataFrame("-", index=nomi, columns=cols)
    
    # Configurazione parametri
    targ_ore = {n: r['ore']*4 for n, r in op_df.set_index('nome').iterrows()}
    lim_n = {n: r['max_notti'] for n, r in op_df.set_index('nome').iterrows()}
    puo_n = {n: r['fa_notti'] for n, r in op_df.set_index('nome').iterrows()}
    vinc_map = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in op_df.set_index('nome').iterrows()}
    
    ore_att, notti_att, stato_ciclo = {n: 0 for n in nomi}, {n: 0 for n in nomi}, {n: 0 for n in nomi}
    we_lav = {n: set() for n in nomi}
    num_we_tot = len([g for g in range(1, num_g + 1) if calendar.weekday(anno, mese, g) == 5])

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        is_we, we_id = wd >= 5, g // 7
        occ_oggi = []

        # A. CICLO NOTTE (Seconda notte obbligatoria N2)
        for n in nomi:
            if stato_ciclo[n] == 1: # Se ieri ha fatto N1, oggi fa N2
                res.at[n, col] = "N"; occ_oggi.append(n); notti_att[n]+=1; ore_att[n]+=9; stato_ciclo[n]=2
                if is_we: we_lav[n].add(we_id)
            elif stato_ciclo[n] == 2: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=3 # Smonto
            elif stato_ciclo[n] == 3: res.at[n, col] = " "; occ_oggi.append(n); stato_ciclo[n]=0 # Riposo

        # B. PREFERENZE (Turni Forzati)
        for _, p in pref_df[pref_df['Giorno'].astype(str) == str(g)].iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8)
                if t == "N": notti_att[n]+=1; stato_ciclo[n]=1
                if is_we: we_lav[n].add(we_id)

        # C. ASSEGNAZIONE AUTOMATICA (N:1, M:2, P:2)
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi if n not in occ_oggi]
                cand_f = []
                for n in cand:
                    v = vinc_map.get(n, [])
                    ok = True
                    # Check Assenze
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): ok = False
                    # Check Notti (Limiti e Abilitazione)
                    if t_tipo == "N":
                        if not puo_n[n] or notti_att[n] >= lim_n[n]: ok = False
                    # Check Vincoli Orari
                    if is_we and "no weekend" in v: ok = False
                    if t_tipo == "M" and ("solo pomeriggio" in v or "no mattina" in v): ok = False
                    if t_tipo == "P" and ("solo mattina" in v or "no pomeriggio" in v): ok = False
                    # Check Incompatibilità
                    for o in occ_oggi:
                        if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==o)) | ((inc_df['Op A']==o) & (inc_df['Op B']==n))].empty: ok = False
                    if ok: cand_f.append(n)
                
                if not cand_f: break
                
                # --- CUORE DEL BILANCIAMENTO V62 ---
                if t_tipo == "N":
                    # Priorità assoluta a chi ha fatto MENO notti finora
                    scelto = min(cand_f, key=lambda x: (notti_att[x], ore_att[x]/targ_ore[x]))
                    notti_att[scelto] += 1
                    stato_ciclo[scelto] = 1 # Attiva N1
                else:
                    # Priorità a chi è più "indietro" con le ore contrattuali
                    scelto = min(cand_f, key=lambda x: ore_att[x]/targ_ore[x] if targ_ore[x]>0 else 99)
                
                res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                if is_we: we_lav[scelto].add(we_id)

    # Analisi Finale
    an_rows = []
    for n in nomi:
        r = res.loc[n].tolist()
        n_c, m_c, p_c = r.count("N"), r.count("M"), r.count("P")
        o_e = (n_c*9) + (m_c*7) + (p_c*8)
        an_rows.append({
            "Operatore": n, 
            "Notti": n_c, 
            "Max Notti": lim_n[n], 
            "Ore Eff.": o_e, 
            "Ore Target": targ_ore[n], 
            "Sat %": round(o_e/targ_ore[n]*100, 1) if targ_ore[n]>0 else 0,
            "WE Libero": "X" if len(we_lav[n]) < num_we_tot else ""
        })
    
    return res, pd.DataFrame(an_rows).set_index("Operatore")

# --- UI OUTPUT ---
mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
m_n = st.sidebar.selectbox("Mese", mesi, index=datetime.now().month - 1)
anno = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=2026)

if st.button("🚀 GENERA PIANO V62"):
    tab, an = genera_v62(anno, mesi.index(m_n) + 1)
    st.subheader("📅 Tabellone Turni")
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("✅ Verifica Copertura (2-2-1)")
    check = pd.DataFrame([{"G": c, "M": tab[c].tolist().count("M"), "P": tab[c].tolist().count("P"), "N": tab[c].tolist().count("N")} for c in tab.columns]).set_index("G").T
    st.table(check)
    
    st.subheader("📊 Analisi Finale Bilanciata")
    st.table(an)
    st.download_button("📥 Scarica Excel", data=to_excel(tab, an), file_name=f"Turni_{m_n}_V62.xlsx")
