import streamlit as st
import pandas as pd
import calendar
from io import BytesIO

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestione Turni - Regola Notte/Riposo", layout="wide")
st.title("🗓️ Generatore Turni: Regola Notte ➔ Smonto ➔ Riposo")

# --- DATABASE OPERATORI INIZIALE ---
if 'operatori' not in st.session_state:
    st.session_state.operatori = [
        {"nome": "NERI ELENA", "ore": 38, "vincoli": ["No Pomeriggio", "Fa Notti", "No Weekend"]},
        {"nome": "RISTOVA SIMONA", "ore": 38, "vincoli": ["No Weekend", "Solo Mattina"]},
        {"nome": "CAMMARATA M.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "MISELMI H.", "ore": 38, "vincoli": ["Fa Notti"]},
        {"nome": "SAKLI BESMA", "ore": 38, "vincoli": []},
        {"nome": "BERTOLETTI B.", "ore": 30, "vincoli": []},
        {"nome": "PALMIERI J.", "ore": 28, "vincoli": []},
        {"nome": "MOSTACCHI M.", "ore": 25, "vincoli": []}
    ]

# --- 1. SEZIONE INPUT ---
st.subheader("👥 1. Configurazione Personale e Vincoli")
edited_df = st.data_editor(
    pd.DataFrame(st.session_state.operatori),
    num_rows="dynamic",
    column_config={
        "nome": st.column_config.TextColumn("Nome Operatore"),
        "ore": st.column_config.NumberColumn("Ore Settimanali"),
        "vincoli": st.column_config.MultiselectColumn(
            "Vincoli",
            options=[
                "No Weekend", "Solo Mattina", "Solo Pomeriggio", "Solo Notti", 
                "Fa Notti", "No Mattina", "No Pomeriggio", "No Notte"
            ]
        )
    },
    key="editor_v7"
)

# --- FUNZIONE LOGICA CON REGOLA SMONTO+RIPOSO ---
def calcola_punteggio_equo(op, tipo_turno, is_weekend, ore_tot_mese, g_idx, res_df, giorni_cols):
    v_raw = op.get('vincoli', [])
    v = [str(i).lower().strip() for i in v_raw] if isinstance(v_raw, list) else []
    nome = op['nome']
    target_mese = op.get('ore', 0) * 4 
    
    # --- REGOLA RIGIDA: DOPO NOTTE -> SMONTO + RIPOSO ---
    if g_idx > 0:
        # Se ieri ha fatto Notte, oggi è SMONTO (non può lavorare)
        if res_df.at[nome, giorni_cols[g_idx-1]] == "N":
            return 999999
    if g_idx > 1:
        # Se l'altro ieri ha fatto Notte, ieri era SMONTO, quindi oggi deve essere RIPOSO
        if res_df.at[nome, giorni_cols[g_idx-2]] == "N":
            return 999999

    # --- VINCOLI RIGIDI STANDARD ---
    if is_weekend and "no weekend" in v: return 999999
    if "solo notti" in v and tipo_turno != "N": return 999999
    if "solo mattina" in v and tipo_turno != "M": return 999999
    if "solo pomeriggio" in v and tipo_turno != "P": return 999999
    if tipo_turno == "N" and not ("fa notti" in v or "solo notti" in v): return 999999
    if tipo_turno == "M" and "no mattina" in v: return 999999
    if tipo_turno == "P" and "no pomeriggio" in v: return 999999

    # --- BILANCIAMENTO ---
    percentuale_carico = ore_tot_mese / target_mese if target_mese > 0 else 0
    punteggio = percentuale_carico * 100 

    # Rotazione Notti (almeno 4 giorni tra una notte e l'altra)
    if tipo_turno == "N":
        for i in range(max(0, g_idx-4), g_idx):
            if res_df.at[nome, giorni_cols[i]] == "N":
                punteggio += 80 

    # Priorità feriale per Neri/Ristova
    if not is_weekend and "no weekend" in v:
        punteggio -= 40 

    return punteggio

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Turni')
    return output.getvalue()

# --- GENERAZIONE ---
if st.button("🚀 GENERA TURNI (CON REGOLA SMONTO+RIPOSO)"):
    anno, mese = 2026, 4
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_cols = [f"{g}-{calendar.day_name[calendar.weekday(anno, mese, g)][:3]}" for g in range(1, num_giorni + 1)]
    
    op_validi = edited_df[edited_df['nome'].notna() & (edited_df['nome'] != "")].copy()
    res_df = pd.DataFrame("-", index=op_validi['nome'].tolist(), columns=giorni_cols)
    ore_tot_mese = {n: 0 for n in op_validi['nome']}

    for g_idx, col in enumerate(giorni_cols):
        is_we = calendar.weekday(anno, mese, g_idx + 1) >= 5
        oggi_assegnati = []

        # Ordine: Notte (più difficile da coprire), poi Mattina e Pomeriggio
        for turno, ore_t, posti in [("N", 9, 1), ("M", 7, 2), ("P", 8, 2)]:
            candidati = []
            for _, op in op_validi.iterrows():
                if op['nome'] not in oggi_assegnati:
                    score = calcola_punteggio_equo(op, turno, is_we, ore_tot_mese[op['nome']], g_idx, res_df, giorni_cols)
                    if score < 900000:
                        candidati.append((op['nome'], score))
            
            candidati.sort(key=lambda x: x[1])
            for s, _ in candidati[:posti]:
                res_df.at[s, col] = turno
                ore_tot_mese[s] += ore_t
                oggi_assegnati.append(s)

    # --- VISUALIZZAZIONE ---
    st.subheader("📅 2. Tabella Turni")
    st.dataframe(res_df)
    
    res_df["ORE TOT"] = res_df.apply(lambda r: (r.tolist().count("M")*7 + r.tolist().count("P")*8 + r.tolist().count("N")*9), axis=1)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📊 Analisi Carico")
        analisi = pd.DataFrame({
            "Target Mensile": op_validi.set_index('nome')['ore'] * 4,
            "Ore Effettive": res_df["ORE TOT"]
        })
        analisi["% Saturazione"] = (analisi["Ore Effettive"] / analisi["Target Mensile"] * 100).round(1).astype(str) + "%"
        st.table(analisi)
    
    with col2:
        st.subheader("📥 Download")
        st.download_button("Scarica Excel", to_excel(res_df), f"turni_regolamentari_{mese}.xlsx")
