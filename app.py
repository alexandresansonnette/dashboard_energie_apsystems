import json
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path
import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from apsystems_api import APSystemsClient, APSystemsError
from storage import save_snapshot

# -----------------------------------------------------------------------
# .env
# -----------------------------------------------------------------------
load_dotenv()

APS_APP_ID     = os.getenv("APS_APP_ID", "")
APS_APP_SECRET = os.getenv("APS_APP_SECRET", "")
SID            = os.getenv("APS_SYSTEM_ID") or ""
METER_EID      = os.getenv("APS_METER_EID") or ""
STORAGE_EID    = os.getenv("APS_STORAGE_EID") or ""

# -----------------------------------------------------------------------
# Tarifs historique
# -----------------------------------------------------------------------
TARIFS_FILE = Path("data/tarifs_historique.json")

TARIFS_DEFAULT = {
    "edf_hphc": [
        {"date_debut": "2025-02-01", "label": "EDF HP/HC 12kVA — fév. 2025",
         "abo_mensuel": 23.32, "hp_cts": 20.65, "hc_cts": 15.79, "ratio_hp": 0.50, "ratio_hc": 0.50},
        {"date_debut": "2025-08-01", "label": "EDF HP/HC 12kVA — août 2025",
         "abo_mensuel": 26.84, "hp_cts": 20.80, "hc_cts": 16.34, "ratio_hp": 0.50, "ratio_hc": 0.50},
        {"date_debut": "2026-02-01", "label": "EDF HP/HC 12kVA — fév. 2026",
         "abo_mensuel": 23.32, "hp_cts": 20.65, "hc_cts": 15.79, "ratio_hp": 0.50, "ratio_hc": 0.50},
    ],
    "urban_solar": [
        {"date_debut": "2026-01-20", "label": "Urban Solar — jan. 2026",
         "abo_mensuel": 49.09, "abo_reseau": 34.69, "abo_stockage": 14.40,
         "hp_cts": 20.80, "hc_cts": 16.34,
         "acheminement_hp_cts": 9.63, "acheminement_hc_cts": 7.90,
         "ratio_hp": 0.50, "ratio_hc": 0.50, "frais_ouverture": 249.0},
        {"date_debut": "2026-02-01", "label": "Urban Solar — fév. 2026",
         "abo_mensuel": 39.78, "abo_reseau": 25.38, "abo_stockage": 14.40,
         "hp_cts": 20.65, "hc_cts": 15.79,
         "acheminement_hp_cts": 9.63, "acheminement_hc_cts": 7.90,
         "ratio_hp": 0.50, "ratio_hc": 0.50, "frais_ouverture": 0.0},
    ]
}

def load_tarifs():
    TARIFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TARIFS_FILE.exists():
        try:
            return json.loads(TARIFS_FILE.read_text("utf-8"))
        except Exception:
            pass
    TARIFS_FILE.write_text(json.dumps(TARIFS_DEFAULT, ensure_ascii=False, indent=2), "utf-8")
    return TARIFS_DEFAULT

def save_tarifs(t):
    TARIFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARIFS_FILE.write_text(json.dumps(t, ensure_ascii=False, indent=2), "utf-8")

def get_pertes(tarifs):
    """Lit le coefficient de pertes câblage depuis le JSON."""
    return tarifs.get("pertes_cable_pct", 3.2)

def get_tarif_for_month(tarifs_list, ym):
    applicable = None
    for t in sorted(tarifs_list, key=lambda x: x["date_debut"]):
        if t["date_debut"][:7] <= ym:
            applicable = t
    return applicable

# -----------------------------------------------------------------------
# Config Streamlit
# -----------------------------------------------------------------------
st.set_page_config(page_title="Pilotage énergie", page_icon="⚡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

/* BASE — tout le monde hérite */
html, body { font-size: 18px !important; }

*, *::before, *::after {
    font-family: 'DM Sans', sans-serif !important;
}

/* Streamlit containers */
.main .block-container { font-size: 18px !important; }
.main .block-container p  { font-size: 18px !important; line-height: 1.7 !important; }
.main .block-container li { font-size: 18px !important; }
.main .block-container label { font-size: 18px !important; font-weight: 500 !important; }

/* Forcer TOUS les éléments Streamlit */
[class^="st"], [class*=" st"] { font-size: 18px !important; }
div[data-testid] { font-size: 18px !important; }
div[data-testid] p { font-size: 18px !important; }
div[data-testid] label { font-size: 18px !important; }
div[data-testid] span { font-size: 18px !important; }

/* Inputs */
input, select, textarea, button { font-size: 18px !important; }
[data-baseweb] { font-size: 18px !important; }
[data-baseweb] * { font-size: 18px !important; }

/* Warnings / alerts */
div[role="alert"] p { font-size: 18px !important; }
div[role="alert"] { font-size: 18px !important; }

/* Sidebar */
section[data-testid="stSidebar"] { 
    background: linear-gradient(180deg, #b8d4ef 0%, #d4e9f7 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.6);
}
section[data-testid="stSidebar"] * { font-size: 18px !important; }

/* Fond ciel */
.stApp {
    background: linear-gradient(180deg, #c9dff5 0%, #e8f4fd 35%, #f0f8ff 60%, #daeef9 100%);
    min-height: 100vh;
}

/* Titres */
h1 { font-family: 'Space Mono', monospace !important; 
     font-size: 2rem !important; color: #1a3a5c !important; letter-spacing: -0.5px; }
h2, h3 { color: #1a3a5c !important; font-size: 1.4rem !important; }

/* Cartes métriques */
.metric-card {
    background: rgba(255,255,255,0.80);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.95);
    border-radius: 14px; padding: 22px 26px; margin-bottom: 14px;
    box-shadow: 0 2px 14px rgba(100,160,220,0.12);
}
.metric-card .label {
    font-size: 0.85rem !important; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #5b7a99; margin-bottom: 10px;
}
.metric-card .value {
    font-family: 'Space Mono', monospace !important;
    font-size: 2.4rem !important; font-weight: 700; color: #1a3a5c; line-height: 1;
}
.metric-card .unit  { font-size: 1.1rem !important; color: #7a9bbf; margin-left: 6px; }
.metric-card .sub   { font-size: 1rem !important; color: #7a9bbf; margin-top: 8px; }

.accent-green  { border-left: 4px solid #059669; }
.accent-blue   { border-left: 4px solid #2563eb; }
.accent-orange { border-left: 4px solid #d97706; }
.accent-red    { border-left: 4px solid #dc2626; }
.accent-purple { border-left: 4px solid #7c3aed; }
.accent-cyan   { border-left: 4px solid #0891b2; }
.accent-gold   { border-left: 4px solid #b45309; }

.info-band {
    background: rgba(255,255,255,0.70); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.95); border-radius: 12px;
    padding: 20px 26px; margin-bottom: 24px; display: flex; gap: 36px; flex-wrap: wrap;
}
.info-band .item { display: flex; flex-direction: column; }
.info-band .item .lbl {
    font-size: 0.88rem !important; text-transform: uppercase;
    letter-spacing: 0.08em; color: #5b7a99; margin-bottom: 6px;
}
.info-band .item .val {
    font-family: 'Space Mono', monospace !important;
    font-size: 1.1rem !important; color: #1a3a5c; font-weight: 600;
}

.section-title {
    font-family: 'Space Mono', monospace !important; font-size: 0.95rem !important;
    text-transform: uppercase; letter-spacing: 0.10em; color: #4a7a9b;
    border-bottom: 2px solid rgba(74,122,155,0.25);
    padding-bottom: 12px; margin: 32px 0 20px 0;
}

.gain-banner {
    background: rgba(255,255,255,0.80); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.98); border-radius: 16px;
    padding: 28px 32px; margin: 18px 0;
    box-shadow: 0 4px 20px rgba(100,160,220,0.15);
}
.gain-banner .big { font-family: 'Space Mono', monospace !important;
                    font-size: 3.4rem !important; font-weight: 700; }
.gain-banner .positive { color: #059669; }
.gain-banner .negative { color: #dc2626; }
.gain-banner .detail   { font-size: 1.1rem !important; color: #2d4a6b; margin-top: 12px; }

.stock-banner {
    background: rgba(8,145,178,0.08);
    border: 1px solid rgba(8,145,178,0.25); border-radius: 14px;
    padding: 22px 28px; margin: 14px 0;
}

/* Boutons */
.stButton > button {
    background: rgba(255,255,255,0.85) !important; color: #1a3a5c !important;
    border: 1px solid rgba(100,160,220,0.4) !important; border-radius: 10px !important;
    font-size: 18px !important; font-weight: 600 !important;
    padding: 10px 24px !important;
}
.stButton > button:hover {
    background: #2563eb !important; color: #fff !important;
    border-color: #2563eb !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: transparent; gap: 6px; }
.stTabs [data-baseweb="tab"] {
    background: rgba(255,255,255,0.55) !important; color: #4a7a9b !important;
    font-size: 17px !important; font-weight: 600 !important;
    border-radius: 8px !important; padding: 10px 22px !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,255,255,0.95) !important; color: #1a3a5c !important;
    box-shadow: 0 1px 8px rgba(100,160,220,0.18) !important;
}

/* Tableaux */
[data-testid="stDataFrame"] { font-size: 17px !important; }
[data-testid="stDataFrame"] * { font-size: 17px !important; }
.dvn-scroller { font-size: 17px !important; }

/* Expander */
details summary { font-size: 18px !important; color: #4a7a9b !important; }
details summary * { font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------
st.markdown("# ⚡ Pilotage énergie")
st.markdown(
    "<p style='color:#4a7a9b;font-size:1rem;margin-top:-10px;'>"
    "APsystems + Urban Solar — tableau de bord</p>",
    unsafe_allow_html=True
)

if not APS_APP_ID or not APS_APP_SECRET:
    st.error("APS_APP_ID ou APS_APP_SECRET manquant dans le fichier .env")
    st.stop()

client = APSystemsClient(app_id=APS_APP_ID, app_secret=APS_APP_SECRET)

# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<p style='font-family:Space Mono;font-size:0.8rem;text-transform:uppercase;"
        "letter-spacing:0.1em;color:#4a7a9b;'>Configuration</p>",
        unsafe_allow_html=True
    )
    sid_input     = st.text_input("System ID",   value=SID)
    meter_input   = st.text_input("Meter EID",   value=METER_EID)
    storage_input = st.text_input("Storage EID", value=STORAGE_EID)
    year = st.number_input("Année analysée", min_value=2020, max_value=2100,
                           value=date.today().year)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def as_float(x):
    try: return float(x)
    except: return 0.0

def fmt(v, dec=1):
    return f"{v:,.{dec}f}".replace(",", "\u202f")

def card(label, value, unit, sub="", accent="accent-blue"):
    return (
        f"<div class='metric-card {accent}'>"
        f"<div class='label'>{label}</div>"
        f"<div class='value'>{value}<span class='unit'>{unit}</span></div>"
        + (f"<div class='sub'>{sub}</div>" if sub else "")
        + "</div>"
    )

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.60)",
    font=dict(family="DM Sans", color="#2d4a6b", size=16),
    xaxis=dict(
        gridcolor="rgba(100,160,220,0.2)", zerolinecolor="rgba(100,160,220,0.3)",
        tickfont=dict(size=15), title_font=dict(size=16),
    ),
    yaxis=dict(
        gridcolor="rgba(100,160,220,0.2)", zerolinecolor="rgba(100,160,220,0.3)",
        tickfont=dict(size=15), title_font=dict(size=16),
    ),
    legend=dict(bgcolor="rgba(255,255,255,0.80)", font=dict(size=15, color="#2d4a6b")),
    margin=dict(l=10, r=10, t=50, b=10),
)

MOIS_FR = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]

def mois_label(m):
    try: return MOIS_FR[int(m)-1]
    except: return str(m)

# -----------------------------------------------------------------------
# Onglets
# -----------------------------------------------------------------------
tab_install, tab_resume, tab_gains, tab_tarifs = st.tabs([
    "🔧 Installation", "📋 Résumé annuel", "💰 Gains & Stock", "⚙️ Tarifs"
])

# ===========================
# Onglet 1 — Installation
# ===========================
with tab_install:
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Informations de ton installation APsystems — ECU, onduleurs, compteurs.</p>",
        unsafe_allow_html=True
    )

    if not sid_input:
        st.warning("Renseigne le System ID dans la barre latérale.")
    else:
        if st.button("🔄 Charger les données installation"):
            try:
                with st.spinner("Connexion à APsystems…"):
                    details   = client.get_system_details(sid_input)
                    summary   = client.get_system_summary(sid_input)
                    inverters = client.get_inverters(sid_input)
                    meters    = client.get_meters(sid_input)
                    for src, pl in [("system_details", details), ("system_summary", summary),
                                    ("inverters", inverters), ("meters", meters)]:
                        save_snapshot(src, pl)

                d = details.get("data", {})
                s = summary.get("data", {})
                light_map = {1:"🟢 Normale", 2:"🟡 Alarme", 3:"🔴 Hors ligne", 4:"⚫ Aucune donnée"}

                st.markdown(f"""
                <div class="info-band">
                    <div class="item"><span class="lbl">SID</span>
                        <span class="val">{d.get('sid','—')}</span></div>
                    <div class="item"><span class="lbl">Capacité</span>
                        <span class="val">{d.get('capacity','—')} kWc</span></div>
                    <div class="item"><span class="lbl">Mise en service</span>
                        <span class="val">{d.get('create_date','—')}</span></div>
                    <div class="item"><span class="lbl">Fuseau</span>
                        <span class="val">{d.get('timezone','—')}</span></div>
                    <div class="item"><span class="lbl">État</span>
                        <span class="val">{light_map.get(d.get('light',0),'—')}</span></div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<div class='section-title'>Production aujourd'hui</div>",
                            unsafe_allow_html=True)
                c1,c2,c3,c4 = st.columns(4)
                c1.markdown(card("Aujourd'hui", fmt(as_float(s.get('today',0))), " kWh",
                                 accent="accent-green"), unsafe_allow_html=True)
                c2.markdown(card("Ce mois", fmt(as_float(s.get('month',0))), " kWh",
                                 accent="accent-blue"), unsafe_allow_html=True)
                c3.markdown(card("Cette année", fmt(as_float(s.get('year',0))), " kWh",
                                 accent="accent-orange"), unsafe_allow_html=True)
                c4.markdown(card("Lifetime", fmt(as_float(s.get('lifetime',0))), " kWh",
                                 accent="accent-purple"), unsafe_allow_html=True)

                inv_data = inverters.get("data", [])
                if inv_data:
                    st.markdown("<div class='section-title'>ECU & Onduleurs</div>",
                                unsafe_allow_html=True)
                    for ecu in inv_data:
                        inv_list = ecu.get("inverter", [])
                        st.markdown(
                            f"<p style='font-size:1rem;color:#2d4a6b;margin-bottom:8px;'>"
                            f"ECU : <code style='color:#1a3a5c;font-size:0.95rem;'>"
                            f"{ecu.get('eid','—')}</code> — {len(inv_list)} onduleurs</p>",
                            unsafe_allow_html=True
                        )
                        if inv_list:
                            df_inv = pd.DataFrame(inv_list)[["uid","type"]]
                            df_inv.columns = ["Identifiant onduleur","Modèle"]
                            st.dataframe(df_inv, use_container_width=True, hide_index=True)

                meter_list = meters.get("data", [])
                if meter_list:
                    st.markdown("<div class='section-title'>Compteur (Meter EID)</div>",
                                unsafe_allow_html=True)
                    for m_id in meter_list:
                        st.markdown(
                            f"<p style='font-family:Space Mono;font-size:1rem;"
                            f"color:#1a3a5c;'>📟 {m_id}</p>",
                            unsafe_allow_html=True
                        )

            except APSystemsError as e: st.error(str(e))
            except Exception as e: st.error(f"Erreur : {e}")

# ===========================
# Onglet 2 — Résumé annuel
# ===========================
with tab_resume:
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Totaux produit / consommé / importé / exporté — aujourd'hui, ce mois, cette année, lifetime.</p>",
        unsafe_allow_html=True
    )

    if not sid_input or not meter_input:
        st.warning("Renseigne le System ID et le Meter EID dans la barre latérale.")
    else:
        if st.button("🔄 Charger le résumé compteur"):
            try:
                with st.spinner("Chargement…"):
                    payload = client.get_meter_summary(sid_input, meter_input)
                save_snapshot("meter_summary", payload)
                data = payload.get("data", {})

                for periode, label in [
                    ("today",    "Aujourd'hui"),
                    ("month",    "Ce mois"),
                    ("year",     "Cette année"),
                    ("lifetime", "Depuis l'installation"),
                ]:
                    pdata = data.get(periode, {})
                    if not pdata: continue
                    st.markdown(f"<div class='section-title'>{label}</div>",
                                unsafe_allow_html=True)
                    prod  = as_float(pdata.get("produced",0))
                    conso = as_float(pdata.get("consumed",0))
                    imp   = as_float(pdata.get("imported",0))
                    exp   = as_float(pdata.get("exported",0))
                    self_used = max(prod - exp, 0)
                    tac = self_used/prod*100  if prod  else 0
                    tau = self_used/conso*100 if conso else 0

                    c1,c2,c3,c4 = st.columns(4)
                    c1.markdown(card("Produit",  fmt(prod,0),  " kWh", accent="accent-green"),
                                unsafe_allow_html=True)
                    c2.markdown(card("Consommé", fmt(conso,0), " kWh", accent="accent-blue"),
                                unsafe_allow_html=True)
                    c3.markdown(card("Importé",  fmt(imp,0),   " kWh", accent="accent-orange"),
                                unsafe_allow_html=True)
                    c4.markdown(card("Exporté",  fmt(exp,0),   " kWh", accent="accent-cyan"),
                                unsafe_allow_html=True)
                    if periode in ("year","lifetime"):
                        c5,c6 = st.columns(2)
                        c5.markdown(card("Taux autoconsommation", fmt(tac), " %",
                                        accent="accent-green"), unsafe_allow_html=True)
                        c6.markdown(card("Taux autonomie", fmt(tau), " %",
                                        accent="accent-blue"), unsafe_allow_html=True)

            except APSystemsError as e: st.error(f"Erreur APsystems : {e}")
            except Exception as e: st.error(f"Erreur : {e}")

# ===========================
# Onglet 3 — Gains & Stock
# ===========================
with tab_gains:
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Gain mensuel Urban Solar vs EDF HP/HC, et état de ta batterie virtuelle. "
        "Calcul journalier depuis le <strong>20/01/2026</strong>.</p>",
        unsafe_allow_html=True
    )

    if not sid_input or not meter_input:
        st.warning("Renseigne le System ID et le Meter EID dans la barre latérale.")
    else:
        if st.button("🔄 Calculer les gains"):
            try:
                tarifs_r  = load_tarifs()
                PERTES_CABLE = get_pertes(tarifs_r)
                us_debut  = tarifs_r["urban_solar"][0]["date_debut"]  # "2026-01-20"

                # Mois à charger jusqu'au mois courant
                mois_a_charger = [m for m in range(1,13)
                                  if f"{year}-{m:02d}" <= f"{year}-{date.today().month:02d}"]

                rows_daily = []
                with st.spinner(f"Chargement journalier — {len(mois_a_charger)} appels API…"):
                    for m in mois_a_charger:
                        ym = f"{year}-{m:02d}"
                        try:
                            p = client.get_meter_period(
                                sid=sid_input, eid=meter_input,
                                energy_level="daily", date_range=ym,
                            )
                            save_snapshot("meter_daily", p, level="daily", date_range=ym)
                            dd = p.get("data", {})
                            times = dd.get("time", [])
                            for i,t in enumerate(times):
                                rows_daily.append({
                                    "date":         f"{year}-{m:02d}-{int(t):02d}",
                                    "mois":         m,
                                    "produit_kwh":  as_float(dd.get("produced",  [0]*99)[i] if i < len(dd.get("produced",[])) else 0),
                                    "consomme_kwh": as_float(dd.get("consumed",  [0]*99)[i] if i < len(dd.get("consumed",[])) else 0),
                                    "importe_kwh":  as_float(dd.get("imported",  [0]*99)[i] if i < len(dd.get("imported",[])) else 0),
                                    "exporte_kwh":  as_float(dd.get("exported",  [0]*99)[i] if i < len(dd.get("exported",[])) else 0),
                                })
                        except Exception as em:
                            st.warning(f"Mois {ym} : {em}")

                if not rows_daily:
                    st.warning("Aucune donnée journalière.")
                    st.stop()

                df_daily = pd.DataFrame(rows_daily)

                # Date de référence Urban Solar pour comparaison stock
                # Urban Solar affiche 927 kWh au 22/05/2026 — on coupe à cette date
                US_REF_DATE  = "2026-05-22"
                US_REF_STOCK = 927

                # Calcul stock virtuel jour par jour depuis us_debut
                df_us = df_daily[df_daily["date"] >= us_debut].copy()
                stock = 0.0
                for idx, row in df_us.iterrows():
                    # Appliquer le coefficient de pertes câblage (onduleur → compteur Enedis)
                    coeff_pertes = 1 - (PERTES_CABLE / 100)
                    export_net = row["exporte_kwh"] * coeff_pertes
                    stock += export_net
                    rep    = min(stock, row["importe_kwh"])
                    stock -= rep
                    df_us.at[idx, "reprise_kwh"]    = rep
                    df_us.at[idx, "hors_stock_kwh"] = max(row["importe_kwh"] - rep, 0)
                    df_us.at[idx, "stock_fin_kwh"]  = stock

                # Stock au 22/05 pour comparaison avec Urban Solar
                stock_au_22mai = df_us[df_us["date"] <= US_REF_DATE]["stock_fin_kwh"].iloc[-1]                     if not df_us[df_us["date"] <= US_REF_DATE].empty else None

                # Agrégation mensuelle
                rows = []
                for m in mois_a_charger:
                    ym   = f"{year}-{m:02d}"
                    dm   = df_daily[df_daily["mois"] == m]
                    dm_us= df_us[df_us["mois"] == m]
                    if dm.empty: continue

                    prod  = dm["produit_kwh"].sum()
                    conso = dm["consomme_kwh"].sum()
                    imp   = dm["importe_kwh"].sum()
                    exp   = dm["exporte_kwh"].sum()
                    if prod == 0 and conso == 0: continue

                    edf_t = get_tarif_for_month(tarifs_r["edf_hphc"], ym)
                    hp_p  = edf_t["hp_cts"]/100 if edf_t else 0.2065
                    hc_p  = edf_t["hc_cts"]/100 if edf_t else 0.1579
                    rh    = edf_t["ratio_hp"]    if edf_t else 0.5
                    rc    = edf_t["ratio_hc"]    if edf_t else 0.5
                    abo_e = edf_t["abo_mensuel"] if edf_t else 23.32
                    cout_edf = conso*(rh*hp_p + rc*hc_p) + abo_e

                    us_t = get_tarif_for_month(tarifs_r["urban_solar"], ym)
                    if us_t and ym >= us_debut[:7]:
                        ach_hp = us_t.get("acheminement_hp_cts", 9.63)/100
                        ach_hc = us_t.get("acheminement_hc_cts", 7.90)/100
                        us_hp  = us_t.get("hp_cts", hp_p*100)/100
                        us_hc  = us_t.get("hc_cts", hc_p*100)/100
                        us_rh  = us_t.get("ratio_hp", 0.5)
                        us_rc  = us_t.get("ratio_hc", 0.5)
                        abo_u  = us_t["abo_mensuel"]

                        if ym == us_debut[:7]:
                            dd_day = int(us_debut[8:10])
                            nb_j   = calendar.monthrange(year, m)[1]
                            abo_u  = abo_u * (nb_j - dd_day + 1) / nb_j

                        rep_m   = dm_us["reprise_kwh"].sum()    if not dm_us.empty else 0
                        hors_m  = dm_us["hors_stock_kwh"].sum() if not dm_us.empty else imp
                        stk_fin = dm_us["stock_fin_kwh"].iloc[-1] if not dm_us.empty else 0
                        cout_us = rep_m*(us_rh*ach_hp + us_rc*ach_hc) + hors_m*(us_rh*us_hp + us_rc*us_hc) + abo_u
                    else:
                        rep_m = 0; hors_m = imp; stk_fin = 0; cout_us = cout_edf

                    rows.append({
                        "Mois":                   mois_label(m),
                        "Produit kWh":            round(prod),
                        "Consommé kWh":           round(conso),
                        "Importé kWh":            round(imp),
                        "Exporté kWh":            round(exp),
                        "Repris stock kWh":       round(rep_m),
                        "Stock virtuel fin kWh":  round(stk_fin),
                        "Coût EDF HP/HC (€)":     round(cout_edf, 2),
                        "Coût Urban Solar (€)":   round(cout_us,  2),
                        "Gain mensuel (€)":       round(cout_edf - cout_us, 2),
                    })

                df_sim = pd.DataFrame(rows)
                tot_edf   = df_sim["Coût EDF HP/HC (€)"].sum()
                tot_us    = df_sim["Coût Urban Solar (€)"].sum()
                tot_gain  = df_sim["Gain mensuel (€)"].sum()
                frais_us  = tarifs_r["urban_solar"][0].get("frais_ouverture", 249)
                gain_net  = tot_gain - frais_us
                stk_actuel= df_sim["Stock virtuel fin kWh"].iloc[-1]

                # ---- Bannière gain ----
                gc = "positive" if tot_gain >= 0 else "negative"
                st.markdown(f"""
                <div class="gain-banner">
                    <div style="color:#4a7a9b;font-size:0.85rem;text-transform:uppercase;
                                letter-spacing:0.1em;margin-bottom:10px;">
                        Gain cumulé {year} — Urban Solar vs EDF HP/HC
                    </div>
                    <div class="big {gc}">+{fmt(tot_gain,0)} €</div>
                    <div class="detail">
                        EDF : <strong>{fmt(tot_edf,0)} €</strong>
                        &nbsp;→&nbsp;
                        Urban Solar : <strong>{fmt(tot_us,0)} €</strong>
                        &nbsp;|&nbsp;
                        Gain net (après frais ouverture {fmt(frais_us,0)} €) :
                        <strong style="color:{'#059669' if gain_net>=0 else '#dc2626'};">
                            {fmt(gain_net,0)} €
                        </strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ---- Vérification coefficient pertes ----
                with st.expander("🔧 Vérifier et ajuster le coefficient de pertes câblage"):
                    st.markdown(
                        "<p style='color:#4a7a9b;font-size:1rem;'>"
                        "Compare ton stock calculé avec la valeur affichée dans l'app Urban Solar "
                        "pour ajuster le coefficient de pertes (onduleur → compteur Enedis).</p>",
                        unsafe_allow_html=True
                    )
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        us_stock_reel = st.number_input(
                            "Stock Urban Solar app (kWh)",
                            value=927.0, step=1.0,
                            help="Valeur affichée dans l'app Urban Solar à une date donnée"
                        )
                        us_stock_date = st.text_input(
                            "Date de référence (YYYY-MM-DD)",
                            value="2026-05-22"
                        )
                    with col_v2:
                        # Stock calculé à cette date
                        try:
                            stock_ref = df_us[df_us["date"] <= us_stock_date]["stock_fin_kwh"].iloc[-1]
                        except:
                            stock_ref = stk_actuel
                        st.markdown(
                            f"<div class='metric-card accent-cyan'>"
                            f"<div class='label'>Mon calcul à cette date</div>"
                            f"<div class='value'>{fmt(stock_ref,0)}<span class='unit'> kWh</span></div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    with col_v3:
                        ecart_v = stock_ref - us_stock_reel
                        # Recalcul du vrai coefficient
                        # stock_ref = export_total * (1 - pertes) - reprises
                        # On approxime : pertes_réelles = ecart / export_total
                        export_total = df_us["exporte_kwh"].sum()
                        if export_total > 0 and ecart_v > 0:
                            pertes_reelles = (ecart_v / (export_total * (1 - PERTES_CABLE/100))) * 100 + PERTES_CABLE
                            pertes_reelles = round(pertes_reelles, 1)
                        else:
                            pertes_reelles = PERTES_CABLE
                        couleur = "#059669" if abs(ecart_v) < 30 else "#d97706" if abs(ecart_v) < 100 else "#dc2626"
                        st.markdown(
                            f"<div class='metric-card accent-orange'>"
                            f"<div class='label'>Écart</div>"
                            f"<div class='value' style='color:{couleur};'>{fmt(ecart_v,0)}<span class='unit'> kWh</span></div>"
                            "<div class='sub'>Pertes réelles estimées : " + str(pertes_reelles) + "%<br>"
                            "Coefficient actuel : " + str(PERTES_CABLE) + "%</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    if st.button("✅ Appliquer ce nouveau coefficient de pertes"):
                        t_save = load_tarifs()
                        t_save["pertes_cable_pct"] = pertes_reelles
                        save_tarifs(t_save)
                        st.success(f"Coefficient mis à jour à {pertes_reelles}% — relance le calcul.")

                # ---- Stock batterie virtuelle ----
                ecart_stock = round(stock_au_22mai - US_REF_STOCK, 0) if stock_au_22mai else None
                ecart_txt = ""
                if ecart_stock is not None:
                    signe = "+" if ecart_stock >= 0 else ""
                    couleur = "#059669" if abs(ecart_stock) < 50 else "#d97706" if abs(ecart_stock) < 150 else "#dc2626"
                    ecart_txt = (
                        f"<br><span style='font-size:0.9rem;color:{couleur};font-weight:600;'>"
                        f"Écart vs Urban Solar au 22/05 : {signe}{int(ecart_stock)} kWh</span>"
                    )

                st.markdown(f"""
                <div class="stock-banner">
                    <div style="color:#0891b2;font-size:0.82rem;text-transform:uppercase;
                                letter-spacing:0.1em;margin-bottom:8px;">
                        🔋 Batterie virtuelle Urban Solar
                    </div>
                    <div style="display:flex;gap:40px;align-items:flex-end;flex-wrap:wrap;">
                        <div>
                            <div style="font-size:0.78rem;color:#5b7a99;margin-bottom:4px;">
                                Stock fin du dernier mois complet</div>
                            <div style="font-family:Space Mono;font-size:2rem;font-weight:700;
                                        color:#1a3a5c;">{fmt(stk_actuel,0)} kWh</div>
                        </div>
                        <div>
                            <div style="font-size:0.78rem;color:#5b7a99;margin-bottom:4px;">
                                Mon calcul au 22/05</div>
                            <div style="font-family:Space Mono;font-size:2rem;font-weight:700;
                                        color:#0891b2;">
                                {fmt(stock_au_22mai,0) if stock_au_22mai else "—"} kWh
                            </div>
                        </div>
                        <div>
                            <div style="font-size:0.78rem;color:#5b7a99;margin-bottom:4px;">
                                Urban Solar app (22/05)</div>
                            <div style="font-family:Space Mono;font-size:2rem;font-weight:700;
                                        color:#b45309;">{US_REF_STOCK} kWh</div>
                        </div>
                    </div>
                    <div style="font-size:0.9rem;color:#2d4a6b;margin-top:10px;">
                        {ecart_txt}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ---- KPIs secondaires ----
                c1,c2,c3 = st.columns(3)
                c1.markdown(card("Coût EDF HP/HC",   fmt(tot_edf,0),  " €",
                                 sub="si tu n'avais pas changé", accent="accent-red"),
                            unsafe_allow_html=True)
                c2.markdown(card("Coût Urban Solar", fmt(tot_us,0),   " €",
                                 sub="contrat actuel", accent="accent-green"),
                            unsafe_allow_html=True)
                c3.markdown(card("Gain net",         fmt(gain_net,0), " €",
                                 sub=f"après {fmt(frais_us,0)} € frais ouverture",
                                 accent="accent-gold"),
                            unsafe_allow_html=True)

                # ---- Graphique gains ----
                st.markdown("<div class='section-title'>Gain mensuel</div>",
                            unsafe_allow_html=True)
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(
                    name="EDF HP/HC (€)", x=df_sim["Mois"],
                    y=df_sim["Coût EDF HP/HC (€)"],
                    marker_color="#dc2626", marker_opacity=0.8
                ))
                fig1.add_trace(go.Bar(
                    name="Urban Solar (€)", x=df_sim["Mois"],
                    y=df_sim["Coût Urban Solar (€)"],
                    marker_color="#059669", marker_opacity=0.8
                ))
                fig1.add_trace(go.Scatter(
                    name="Gain (€)", x=df_sim["Mois"],
                    y=df_sim["Gain mensuel (€)"],
                    mode="lines+markers+text",
                    text=[f"+{v}€" for v in df_sim["Gain mensuel (€)"]],
                    textposition="top center",
                    textfont=dict(size=16, color="#b45309"),
                    line=dict(color="#b45309", width=2.5),
                    marker=dict(size=8)
                ))
                fig1.update_layout(barmode="group", **PLOTLY_LAYOUT, height=440,
                                   yaxis_title="€")
                st.plotly_chart(fig1, use_container_width=True)

                # ---- Graphique stock ----
                st.markdown("<div class='section-title'>Évolution du stock virtuel</div>",
                            unsafe_allow_html=True)
                fig2 = go.Figure()
                # Courbe stock — sans texte sur chaque point
                fig2.add_trace(go.Scatter(
                    name="Stock fin de mois (kWh)",
                    x=df_sim["Mois"], y=df_sim["Stock virtuel fin kWh"],
                    mode="lines+markers",
                    line=dict(color="#0891b2", width=3),
                    marker=dict(size=10),
                    fill="tozeroy", fillcolor="rgba(8,145,178,0.10)",
                    hovertemplate="%{x} : <b>%{y} kWh</b><extra></extra>"
                ))
                # Ligne de référence Urban Solar
                fig2.add_hline(
                    y=US_REF_STOCK, line_dash="dash", line_color="#b45309",
                    annotation_text=f"Urban Solar 22/05 : {US_REF_STOCK} kWh",
                    annotation_font_size=14,
                    annotation_position="bottom right"
                )
                # Point au 22/05 — juste le marqueur avec hover
                if stock_au_22mai is not None:
                    fig2.add_trace(go.Scatter(
                        name=f"Mon calcul au 22/05 : {round(stock_au_22mai,0)} kWh",
                        x=["Mai"], y=[round(stock_au_22mai,0)],
                        mode="markers",
                        marker=dict(size=18, color="#b45309", symbol="diamond"),
                        hovertemplate=f"22/05 : <b>{round(stock_au_22mai,0)} kWh</b><extra></extra>"
                    ))
                # Annoter seulement la dernière valeur
                dernier_mois = df_sim["Mois"].iloc[-1]
                dernier_stock = df_sim["Stock virtuel fin kWh"].iloc[-1]
                fig2.add_annotation(
                    x=dernier_mois, y=dernier_stock,
                    text=f"<b>{dernier_stock} kWh</b>",
                    showarrow=True, arrowhead=2,
                    font=dict(size=15, color="#0891b2"),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="#0891b2", borderwidth=1,
                    ay=-40
                )
                layout_fig2 = {k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("xaxis","yaxis","legend")}
                fig2.update_layout(
                    **layout_fig2,
                    xaxis=dict(gridcolor="rgba(100,160,220,0.2)", tickfont=dict(size=15)),
                    yaxis=dict(gridcolor="rgba(100,160,220,0.2)", title="kWh", tickfont=dict(size=15)),
                    legend=dict(bgcolor="rgba(255,255,255,0.8)", font=dict(size=14)),
                    height=380
                )
                st.plotly_chart(fig2, use_container_width=True)

                # ---- Tableau ----
                st.markdown("<div class='section-title'>Détail mensuel</div>",
                            unsafe_allow_html=True)
                st.dataframe(df_sim, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇ Exporter CSV",
                    df_sim.to_csv(index=False).encode("utf-8"),
                    file_name=f"gains_urban_solar_{year}.csv", mime="text/csv"
                )

            except APSystemsError as e: st.error(f"Erreur APsystems : {e}")
            except Exception as e: st.error(f"Erreur inattendue : {e}")

# ===========================
# Onglet 4 — Tarifs
# ===========================
with tab_tarifs:
    tarifs = load_tarifs()

    # ---- Tarifs actuellement en vigueur ----
    st.markdown("<div class='section-title'>Tarifs actuellement en vigueur</div>",
                unsafe_allow_html=True)

    us_actuel  = get_tarif_for_month(tarifs["urban_solar"], date.today().strftime("%Y-%m"))
    edf_actuel = get_tarif_for_month(tarifs["edf_hphc"],    date.today().strftime("%Y-%m"))

    col_us, col_edf = st.columns(2)

    with col_us:
        st.markdown(
            "<p style='color:#059669;font-size:1.1rem;font-weight:700;margin-bottom:12px;'>"
            "☀️ Urban Solar — en vigueur</p>",
            unsafe_allow_html=True
        )
        if us_actuel:
            st.markdown(f"""
            <div class='metric-card accent-green' style='font-size:1rem;'>
                <div style='margin-bottom:8px;'>
                    <span style='color:#5b7a99;font-size:0.85rem;'>Depuis</span><br>
                    <strong>{us_actuel['date_debut']}</strong> — {us_actuel['label']}
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;'>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Abo réseau</span><br>
                        <strong>{us_actuel.get('abo_reseau','—')} €/mois</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Abo stockage</span><br>
                        <strong>{us_actuel.get('abo_stockage','—')} €/mois</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Total abonnement</span><br>
                        <strong style='color:#059669;font-size:1.2rem;'>{us_actuel.get('abo_mensuel','—')} €/mois</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Frais ouverture</span><br>
                        <strong>{us_actuel.get('frais_ouverture',0)} €</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>HP</span><br>
                        <strong>{us_actuel.get('hp_cts','—')} cts/kWh</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>HC</span><br>
                        <strong>{us_actuel.get('hc_cts','—')} cts/kWh</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Ach. HP</span><br>
                        <strong>{us_actuel.get('acheminement_hp_cts','—')} cts/kWh</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Ach. HC</span><br>
                        <strong>{us_actuel.get('acheminement_hc_cts','—')} cts/kWh</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_edf:
        st.markdown(
            "<p style='color:#2563eb;font-size:1.1rem;font-weight:700;margin-bottom:12px;'>"
            "⚡ EDF Tarif Bleu HP/HC — référence</p>",
            unsafe_allow_html=True
        )
        if edf_actuel:
            st.markdown(f"""
            <div class='metric-card accent-blue' style='font-size:1rem;'>
                <div style='margin-bottom:8px;'>
                    <span style='color:#5b7a99;font-size:0.85rem;'>Depuis</span><br>
                    <strong>{edf_actuel['date_debut']}</strong> — {edf_actuel['label']}
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;'>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Abonnement</span><br>
                        <strong style='color:#2563eb;font-size:1.2rem;'>{edf_actuel.get('abo_mensuel','—')} €/mois</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>Ratio HP/HC</span><br>
                        <strong>{int(edf_actuel.get('ratio_hp',0.5)*100)}% / {int(edf_actuel.get('ratio_hc',0.5)*100)}%</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>HP</span><br>
                        <strong>{edf_actuel.get('hp_cts','—')} cts/kWh</strong></div>
                    <div><span style='color:#5b7a99;font-size:0.85rem;'>HC</span><br>
                        <strong>{edf_actuel.get('hc_cts','—')} cts/kWh</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ---- Historique complet ----
    st.markdown("<div class='section-title'>Historique des tarifs</div>",
                unsafe_allow_html=True)

    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;margin-bottom:8px;'>"
        "<strong>Urban Solar</strong></p>",
        unsafe_allow_html=True
    )
    us_rows = []
    for t in tarifs["urban_solar"]:
        us_rows.append({
            "Depuis":           t.get("date_debut", "—"),
            "Abo total €/mois": t.get("abo_mensuel", "—"),
            "Réseau €/mois":    t.get("abo_reseau",  "—"),
            "Stockage €/mois":  t.get("abo_stockage","—"),
            "HP cts":           t.get("hp_cts",       "—"),
            "HC cts":           t.get("hc_cts",       "—"),
            "Ach. HP cts":      t.get("acheminement_hp_cts","—"),
            "Ach. HC cts":      t.get("acheminement_hc_cts","—"),
            "Frais ouv. €":     t.get("frais_ouverture", 0),
        })
    st.dataframe(pd.DataFrame(us_rows), use_container_width=True, hide_index=True)

    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;margin-top:20px;margin-bottom:8px;'>"
        "<strong>EDF Tarif Bleu HP/HC</strong></p>",
        unsafe_allow_html=True
    )
    edf_rows = []
    for t in tarifs["edf_hphc"]:
        edf_rows.append({
            "Depuis":       t.get("date_debut","—"),
            "Abo €/mois":   t.get("abo_mensuel","—"),
            "HP cts":       t.get("hp_cts","—"),
            "HC cts":       t.get("hc_cts","—"),
            "Ratio HP %":   int(t.get("ratio_hp",0.5)*100),
        })
    st.dataframe(pd.DataFrame(edf_rows), use_container_width=True, hide_index=True)

    # ---- Vérification data.gouv.fr ----
    st.markdown("<div class='section-title'>Vérifier les tarifs EDF sur data.gouv.fr</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Interroge le dataset CRE — prochaine révision attendue : <strong>1er août 2026</strong>.</p>",
        unsafe_allow_html=True
    )

    if st.button("🔄 Vérifier les tarifs EDF"):
        try:
            with st.spinner("Interrogation data.gouv.fr…"):
                RID = "f7303b3a-93c7-4242-813d-84919034c416"
                url = (f"https://tabular-api.data.gouv.fr/api/resources/{RID}/data/"
                       f"?P_SOUSCRITE__exact=12&DATE_DEBUT__sort=desc&page_size=5")
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    api_data = json.loads(r.read().decode())

            rows_api = api_data.get("data", [])
            if not rows_api:
                st.warning("Aucune donnée retournée.")
            else:
                def get_col(row, *keys):
                    for k in keys:
                        if k in row and row[k] is not None:
                            return row[k]
                    return None

                disp = []
                for r in rows_api[:5]:
                    hp  = get_col(r,"HP_TTC","PART_VARIABLE_HP_TTC","HEURE_PLEINE_TTC")
                    hc  = get_col(r,"HC_TTC","PART_VARIABLE_HC_TTC","HEURE_CREUSE_TTC")
                    abo = get_col(r,"PART_FIXE_TTC","ABO_TTC")
                    disp.append({
                        "Date début":       r.get("DATE_DEBUT","—"),
                        "Abo annuel TTC €": abo,
                        "Abo mensuel €":    round(float(abo)/12,2) if abo else "—",
                        "HP cts/kWh":       round(float(hp)*100,2) if hp else "—",
                        "HC cts/kWh":       round(float(hc)*100,2) if hc else "—",
                    })
                st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)

                latest = rows_api[0]
                hp_v  = get_col(latest,"HP_TTC","PART_VARIABLE_HP_TTC","HEURE_PLEINE_TTC")
                hc_v  = get_col(latest,"HC_TTC","PART_VARIABLE_HC_TTC","HEURE_CREUSE_TTC")
                abo_v = get_col(latest,"PART_FIXE_TTC","ABO_TTC")
                d_v   = latest.get("DATE_DEBUT","")

                if hp_v and hc_v and abo_v:
                    hp_cts = round(float(hp_v)*100,2)
                    hc_cts = round(float(hc_v)*100,2)
                    abo_m  = round(float(abo_v)/12,2)
                    st.info(f"Tarif le plus récent ({d_v}) : Abo {abo_m} €/mois · HP {hp_cts} cts · HC {hc_cts} cts")
                    if st.button("✅ Appliquer ce tarif EDF"):
                        existing = [t["date_debut"] for t in tarifs["edf_hphc"]]
                        if d_v not in existing:
                            tarifs["edf_hphc"].append({
                                "date_debut": d_v, "label": f"EDF HP/HC 12kVA — {d_v} (data.gouv.fr)",
                                "abo_mensuel": abo_m, "hp_cts": hp_cts, "hc_cts": hc_cts,
                                "ratio_hp": 0.50, "ratio_hc": 0.50,
                            })
                        else:
                            for t in tarifs["edf_hphc"]:
                                if t["date_debut"] == d_v:
                                    t.update({"abo_mensuel": abo_m, "hp_cts": hp_cts, "hc_cts": hc_cts})
                        save_tarifs(tarifs)
                        st.success(f"Tarif {d_v} enregistré.")

        except Exception as e:
            st.error(f"API data.gouv.fr indisponible : {e}")

    # ---- Coefficient de pertes ----
    st.markdown("<div class='section-title'>Coefficient de pertes câblage</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Pertes entre l'onduleur APsystems et le compteur Enedis (câblage interne). "
        "Calculé à 3.2% depuis tes courbes de charge Enedis.</p>",
        unsafe_allow_html=True
    )
    pertes_actuel = tarifs.get("pertes_cable_pct", 3.2)
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        new_pertes = st.number_input(
            "Coefficient de pertes (%)",
            value=float(pertes_actuel),
            min_value=0.0, max_value=10.0, step=0.1,
            help="3.2% mesuré le 22/05/2026 — à re-vérifier de temps en temps"
        )
    with col_p2:
        st.markdown(
            f"<p style='color:#4a7a9b;font-size:0.95rem;padding-top:32px;'>"
            f"Valeur actuelle : <strong>{pertes_actuel}%</strong> — "
            f"impact sur le stock : environ {round(pertes_actuel * 26, 0):.0f} kWh/an "
            f"(basé sur ~2 600 kWh injectés/an)</p>",
            unsafe_allow_html=True
        )
    if st.button("💾 Enregistrer le coefficient de pertes"):
        tarifs["pertes_cable_pct"] = new_pertes
        save_tarifs(tarifs)
        st.success(f"Coefficient mis à jour à {new_pertes}%.")

    # ---- Nouveau tarif Urban Solar ----
    st.markdown("<div class='section-title'>Nouveau tarif Urban Solar</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4a7a9b;font-size:1rem;'>"
        "Quand Urban Solar change ses tarifs, saisis la date de début et les nouveaux montants. "
        "L'ancien tarif reste dans l'historique et continue de s'appliquer aux mois passés.</p>",
        unsafe_allow_html=True
    )

    with st.expander("➕ Ajouter un nouveau tarif Urban Solar"):
        c1, c2 = st.columns(2)
        with c1:
            new_debut = st.text_input(
                "Date de début (YYYY-MM-DD)",
                value=str(date.today()),
                help="Ex: 2026-08-01"
            )
            new_label = st.text_input(
                "Libellé",
                placeholder="Ex: Urban Solar — août 2026"
            )
            n_abo_r = st.number_input("Abo réseau HP/HC TTC (€/mois)",    value=25.38, step=0.01)
            n_abo_s = st.number_input("Abo stockage virtuel TTC (€/mois)", value=14.40, step=0.01)
            n_abo   = round(n_abo_r + n_abo_s, 2)
            st.markdown(
                f"<p style='color:#059669;font-size:1.1rem;font-weight:700;'>"
                f"Total abo : {n_abo} €/mois TTC</p>",
                unsafe_allow_html=True
            )
        with c2:
            n_hp     = st.number_input("Prix HP TTC (cts/kWh)",              value=20.65, step=0.01)
            n_hc     = st.number_input("Prix HC TTC (cts/kWh)",              value=15.79, step=0.01)
            n_ach_hp = st.number_input("Acheminement HP TTC (cts/kWh)",      value=9.63,  step=0.01)
            n_ach_hc = st.number_input("Acheminement HC TTC (cts/kWh)",      value=7.90,  step=0.01)
            n_ouv    = st.number_input("Frais ouverture one-shot (€)",        value=0.0,   step=1.0)

        if st.button("💾 Enregistrer ce nouveau tarif Urban Solar"):
            existing_dates = [t["date_debut"] for t in tarifs["urban_solar"]]
            if new_debut in existing_dates:
                st.error(f"Un tarif Urban Solar existe déjà pour le {new_debut}.")
            else:
                tarifs["urban_solar"].append({
                    "date_debut":          new_debut,
                    "label":               new_label or f"Urban Solar — {new_debut}",
                    "abo_mensuel":         n_abo,
                    "abo_reseau":          n_abo_r,
                    "abo_stockage":        n_abo_s,
                    "hp_cts":              n_hp,
                    "hc_cts":              n_hc,
                    "acheminement_hp_cts": n_ach_hp,
                    "acheminement_hc_cts": n_ach_hc,
                    "frais_ouverture":     n_ouv,
                    "ratio_hp":            0.50,
                    "ratio_hc":            0.50,
                })
                save_tarifs(tarifs)
                st.success(
                    f"✅ Tarif du {new_debut} enregistré. "
                    f"Il s'appliquera à partir de cette date. "
                    f"Les mois passés gardent leurs anciens tarifs."
                )
                st.rerun()

    # ---- Nouveau tarif EDF ----
    with st.expander("➕ Ajouter un nouveau tarif EDF (si révision manuelle)"):
        c1, c2 = st.columns(2)
        with c1:
            edf_debut = st.text_input("Date de début (YYYY-MM-DD)", value=str(date.today()), key="edf_new_d")
            edf_label = st.text_input("Libellé", placeholder="Ex: EDF — août 2026", key="edf_new_l")
            edf_abo   = st.number_input("Abo mensuel TTC (€)", value=23.32, step=0.01, key="edf_new_a")
        with c2:
            edf_hp    = st.number_input("HP TTC (cts/kWh)", value=20.65, step=0.01, key="edf_new_hp")
            edf_hc    = st.number_input("HC TTC (cts/kWh)", value=15.79, step=0.01, key="edf_new_hc")
            edf_rh    = st.slider("Ratio HP (%)", 0, 100, 50, key="edf_new_rh")

        if st.button("💾 Enregistrer ce tarif EDF", key="edf_save_new"):
            tarifs["edf_hphc"].append({
                "date_debut": edf_debut,
                "label":      edf_label or f"EDF HP/HC 12kVA — {edf_debut}",
                "abo_mensuel": edf_abo,
                "hp_cts":      edf_hp,
                "hc_cts":      edf_hc,
                "ratio_hp":    edf_rh/100,
                "ratio_hc":    1-edf_rh/100,
            })
            save_tarifs(tarifs)
            st.success(f"✅ Tarif EDF du {edf_debut} enregistré.")
            st.rerun()
