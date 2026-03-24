import streamlit as st
import pandas as pd
import calendar
import json
import os
from io import BytesIO
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Turni V67.4 - Vincoli Ferrei", layout="wide", page_icon="⚖️")

DB_FILE = "database_turni_v66.json"

def carica_dati():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return None
    return None

def salva_dati(operatori):
    with open(DB_FILE, "w") as f: json.dump(operatori, f)

# --- INIZIALIZZAZIONE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = carica_dati() or []

st.title("⚖️ Sistema Turni V67.4 - Rispetto Vincoli & Copertura")

# --- UI GESTIONE ---
with st.expander("⚙️ 1. Squadra e Incompatibilità"):
    op_df = st.data_editor(pd.DataFrame(st.session_state.operatori), num_rows="dynamic", key="editor_op",
                             column_config={"vincoli": st.column_config.MultiselectColumn("Vincoli", options=["No Weekend", "Solo Mattina", "Solo Pomeriggio", "No Mattina", "No Pomeriggio"]),
                                            "fa_notti": st.column_config.CheckboxColumn("Notti?")})
    lista_nomi = op_df['nome'].dropna().unique().tolist()
    if st.button("💾 Salva Database"):
        st.session_state.operatori = op_df.to_dict('records')
        salva_dati(st.session_state.operatori)
        st.success("Salvataggio effettuato!")

    inc_df = st.data_editor(pd.DataFrame(columns=["Op A", "Op B"]), num_rows="dynamic", key="inc_ed",
                             column_config={"Op A": st.column_config.SelectboxColumn("Op 1", options=lista_nomi),
                                            "Op B": st.column_config.SelectboxColumn("Op 2", options=lista_nomi)})

with st.expander("🃏 2. Gettonisti"):
    gett_input_df = st.data_editor(pd.DataFrame(columns=["Nome Gettonista", "Giorno", "Preferenza Turno"]), num_rows="dynamic", key="gett_ed",
                             column_config={"Preferenza Turno": st.column_config.SelectboxColumn("T", options=["Qualsiasi", "M", "P", "N"])})

col_ass, col_pref = st.columns(2)
with col_ass:
    st.subheader("🚫 Assenze")
    ass_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Dal", "Al"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi)})
with col_pref:
    st.subheader("⭐ Preferenze")
    pref_df = st.data_editor(pd.DataFrame(columns=["Operatore", "Giorno", "Turno"]), num_rows="dynamic",
                             column_config={"Operatore": st.column_config.SelectboxColumn("Op", options=lista_nomi),
                                            "Turno": st.column_config.SelectboxColumn("T", options=["M", "P", "N"])})

# --- MOTORE DI CALCOLO ---
def genera_piano(anno, mese):
    num_g = calendar.monthrange(anno, mese)[1]
    cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_g + 1)]
    nomi_fissi = [o['nome'] for o in st.session_state.operatori if o['nome']]
    res = pd.DataFrame("-", index=nomi_fissi, columns=cols)
    info_m = {o['nome']: o for o in st.session_state.operatori if o['nome']}
    vinc_m = {n: [v.lower() for v in r['vincoli']] if isinstance(r['vincoli'], list) else [] for n, r in info_m.items()}
    
    ore_att, notti_att, stato_c = {n: 0 for n in nomi_fissi}, {n: 0 for n in nomi_fissi}, {n: 0 for n in nomi_fissi}
    
    # Calcolo weekend protetti (ogni operatore ha un weekend assegnato a rotazione)
    weekend_list = []
    for g in range(1, num_g):
        if calendar.weekday(anno, mese, g) == 5: weekend_list.append((g, g+1))
    we_protetto = {n: (weekend_list[i % len(weekend_list)] if weekend_list else -1) for i, n in enumerate(nomi_fissi)}

    for g in range(1, num_g + 1):
        wd, col = calendar.weekday(anno, mese, g), cols[g-1]
        col_prev = cols[g-2] if g > 1 else None
        is_we, occ_oggi = wd >= 5, []

        # A. PREFERENZE (Sempre rispettate)
        p_oggi = pref_df[pref_df['Giorno'].astype(str) == str(g)]
        for _, p in p_oggi.iterrows():
            n, t = p['Operatore'], p['Turno']
            if n in nomi_fissi and n not in occ_oggi:
                res.at[n, col] = t; occ_oggi.append(n); ore_att[n] += (9 if t=="N" else 7 if t=="M" else 8)
                if t == "N": notti_att[n]+=1; stato_c[n]=1

        # B. GESTIONE SMONTO/RIPOSO NOTTE
        for n in nomi_fissi:
            if n in occ_oggi: continue
            if stato_c[n] == 1: # Smonto
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=2
            elif stato_c[n] == 2: # Riposo
                res.at[n, col] = " "; occ_oggi.append(n); stato_c[n]=0

        # C. RIEMPIMENTO 2-2-1 CON VINCOLI FERREI
        for t_tipo, qta in [("N", 1), ("M", 2), ("P", 2)]:
            while res[col].tolist().count(t_tipo) < qta:
                cand = [n for n in nomi_fissi if n not in occ_oggi]
                
                # Sotto-funzione per validare i vincoli HARD
                def is_valido_hard(n, t):
                    v = vinc_m.get(n, [])
                    if any(r['Operatore']==n and pd.notna(r['Dal']) and int(r['Dal'])<=g<=(int(r['Al']) if pd.notna(r['Al']) else int(r['Dal'])) for _, r in ass_df.iterrows()): return False
                    if t == "M" and (col_prev and res.at[n, col_prev] == "P"): return False
                    if t == "M" and ("solo pomeriggio" in v or "no mattina" in v): return False
                    if t == "P" and ("solo mattina" in v or "no pomeriggio" in v): return False
                    if is_we and "no weekend" in v: return False
                    if t == "N" and (not info_m[n]['fa_notti'] or notti_att[n] >= info_m[n]['max_notti']): return False
                    for gia_in in occ_oggi:
                        if not inc_df[((inc_df['Op A']==n) & (inc_df['Op B']==gia_in)) | ((inc_df['Op A']==gia_in) & (inc_df['Op B']==n))].empty: return False
                    return True

                # LIVELLO 1: Fissi disponibili + NO Weekend Protetto
                cand_l1 = [n for n in cand if is_valido_hard(n, t_tipo) and not (n in we_protetto and we_protetto[n] != -1 and g in we_protetto[n])]
                if cand_l1:
                    scelto = min(cand_l1, key=lambda x: (notti_att[x] if t_tipo=="N" else ore_att[x]))
                    res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                    ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                    if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1
                    continue

                # LIVELLO 2: Gettonisti
                get_disp = gett_input_df[(gett_input_df['Giorno'] == g) & ((gett_input_df['Preferenza Turno'] == t_tipo) | (gett_input_df['Preferenza Turno'] == "Qualsiasi"))]
                valido_get = next((r['Nome Gettonista'] + " (GET)" for _, r in get_disp.iterrows() if (r['Nome Gettonista'] + " (GET)") not in occ_oggi), None)
                if valido_get:
                    if valido_get not in res.index: res = pd.concat([res, pd.DataFrame("-", index=[valido_get], columns=res.columns)])
                    res.at[valido_get, col] = t_tipo; occ_oggi.append(valido_get)
                    continue

                # LIVELLO 3: Emergenza Fissi (Ignora weekend protetto MA rispetta Vincoli Ruolo/Assenze)
                cand_l3 = [n for n in cand if is_valido_hard(n, t_tipo)]
                if cand_l3:
                    scelto = min(cand_l3, key=lambda x: ore_att[x])
                    res.at[scelto, col] = t_tipo; occ_oggi.append(scelto)
                    ore_att[scelto] += (9 if t_tipo=="N" else 7 if t_tipo=="M" else 8)
                    if t_tipo == "N": notti_att[scelto]+=1; stato_c[scelto]=1
                    continue
                
                break # Turno scoperto se nessuno rispetta i vincoli HARD

    # Calcolo Weekend Liberi (Smonto Sabato + Domenica)
    we_liberi = {n: sum(1 for sab, dom in weekend_list if res.at[n, cols[sab-1]] in ["-", " ", "R"] and res.at[n, cols[dom-1]] in ["-", " ", "R"]) for n in nomi_fissi}
    return res, ore_att, notti_att, info_m, we_liberi

# --- VISUALIZZAZIONE ---
if st.button("🚀 GENERA PIANO V67.4"):
    tab, ore_f, notti_f, info_f, we_f = genera_piano(anno, mesi.index(m_sel) + 1)
    st.dataframe(tab, use_container_width=True)
    
    st.subheader("📊 Analisi Squadra Fissa")
    an_df = pd.DataFrame([{"Operatore": n, "Notti": notti_f[n], "WE Liberi": we_f[n], "Ore Eff.": ore_f[n], "Target": info_f[n]['ore']*4, "Sat%": round((ore_f[n]/(info_f[n]['ore']*4)*100),1) if info_f[n]['ore']>0 else 0} for n in tab.index if "(GET)" not in n])
    st.table(an_df.set_index("Operatore"))ame=f"Turni_{m_sel}.xlsx")
