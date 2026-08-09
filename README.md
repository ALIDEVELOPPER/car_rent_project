# Gestion Agence de Location de Voitures

Application desktop de gestion pour agence de location de voitures : clients, flotte, réservations, factures, tableau de bord.

## Stack

- Backend : Flask + SQLAlchemy (SQLite en dev)
- Frontend : HTML / CSS / JavaScript (Alpine.js) + Chart.js
- Desktop : pywebview
- Tests : pytest

## Structure

```
backend/    API Flask, modèles, logique métier, tests
frontend/   Pages HTML, CSS, JS statiques
desktop/    Lanceur pywebview
```

## Setup développement

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Le reste (initialisation de la base, lancement du serveur) sera documenté au fur et à mesure de l'avancement des modules.

## État du projet

En cours de développement, module par module. Voir l'historique git pour le détail de l'avancement.
