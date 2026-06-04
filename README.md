# ⚡ Dashboard énergie — APsystems + Urban Solar

Tableau de bord personnel Streamlit pour piloter son installation solaire APsystems et simuler les gains du contrat Urban Solar (stockage virtuel) vs tarif EDF HP/HC.

## Fonctionnalités

- **🔧 Installation** — infos ECU, onduleurs, compteurs, production du jour
- **📋 Résumé annuel** — totaux produit / consommé / importé / exporté (today, mois, année, lifetime)
- **💰 Gains & Stock** — simulation journalière Urban Solar vs EDF HP/HC, évolution du stock virtuel
- **⚙️ Tarifs** — historique tarifaire EDF et Urban Solar, vérification automatique via data.gouv.fr (CRE)

## Prérequis

- Python 3.10+ (ou Miniconda)
- Compte APsystems EMA avec accès OpenAPI activé (Réglages > Service OpenAPI)
- Contrat Urban Solar avec stockage virtuel

## Installation

```bash
cd dashboard_energie_apsystems
pip install -r requirements.txt
copy .env.example .env
```

Édite `.env` avec tes identifiants :

```env
APS_APP_ID=ton_app_id          # Réglages > Service OpenAPI dans EMA
APS_APP_SECRET=ton_app_secret
APS_SYSTEM_ID=ton_sid          # Réglages > Détails du compte > SID
APS_METER_EID=ton_meter_eid    # Récupéré via onglet Installation
APS_STORAGE_EID=               # Laisser vide si pas de batterie physique
```

## Lancement

Double-clic sur `lancer.bat` — ou depuis un terminal :

```bash
cd dashboard_energie_apsystems
streamlit run app.py
```

## Configuration des tarifs

Au premier lancement, le fichier `data/tarifs_historique.json` est créé automatiquement avec les tarifs EDF HP/HC et Urban Solar pré-renseignés pour 12 kVA.

Pour mettre à jour les tarifs : onglet **⚙️ Tarifs** > boutons dédiés.

## Quota API APsystems

- Forfait gratuit : **1 000 appels/mois**
- L'onglet Gains & Stock consomme ~6 appels par clic (1 par mois chargé)
- Les autres onglets : 1 à 4 appels par clic

## Important

- Ne jamais mettre `.env` sur GitHub
- Le dossier `data/` (SQLite + tarifs) est exclu du repo
- Le dossier `.streamlit/` (config locale) est exclu du repo
