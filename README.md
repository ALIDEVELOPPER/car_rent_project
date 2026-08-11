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

```bash
cd backend
flask db upgrade                # crée/migre la base SQLite locale (backend/instance/app.db)
flask create-admin              # amorce le premier compte administrateur
flask run                       # sert l'app sur http://127.0.0.1:5000, testable au navigateur
```

Pour lancer la fenêtre desktop (pywebview) en dev :

```bash
python desktop/main.py
```

Sur Linux + session Wayland, si aucune fenêtre n'apparaît, vérifier que le venv est bien activé et que `QT_QPA_PLATFORM=xcb` est appliqué (déjà géré automatiquement par `desktop/main.py`).

## Packaging (exécutable autonome)

```bash
source venv/bin/activate
pip install pyinstaller
pyinstaller desktop/agence_location.spec --distpath desktop/dist --workpath desktop/build --noconfirm
```

Le résultat est dans `desktop/dist/AgenceLocation/` (mode `--onedir` : un dossier à distribuer, pas un seul fichier). Au premier lancement, l'app crée sa base de données, ses uploads et sa clé secrète dans un dossier de données utilisateur (`~/.local/share/AgenceLocation` sur Linux, `%APPDATA%\AgenceLocation` sur Windows, `~/Library/Application Support/AgenceLocation` sur Mac) — jamais dans le dossier d'installation, qui peut être en lecture seule.

Le `.spec` a été écrit et testé sur Linux, et est conçu pour fonctionner tel quel sur Windows/Mac (imports cachés conditionnés par `sys.platform`). Un exécutable Windows ou Mac doit être **construit sur la plateforme cible respective** (limitation universelle de PyInstaller — impossible de cross-compiler).

### Build automatique Windows / Mac / Linux via GitHub Actions

Le workflow `.github/workflows/build-desktop.yml` construit les trois exécutables en parallèle sur des runners GitHub (Windows, Mac, Linux), sans avoir besoin de ces machines soi-même :

1. Déclenchement manuel depuis l'onglet **Actions** du dépôt GitHub (bouton "Run workflow"), ou automatiquement en poussant un tag `v*` (ex: `v1.0.0`)
2. Chaque build est déposé comme **artifact** téléchargeable depuis la page du run (dossier `desktop/dist/AgenceLocation/` de l'OS correspondant)
3. Ces builds n'ont pas encore été testés en pratique sur Windows/Mac (seul le Linux l'a été de bout en bout) — à valider en lançant l'exécutable téléchargé sur une vraie machine de l'OS concerné avant de le distribuer aux gestionnaires d'agence

## État du projet

En cours de développement, module par module. Voir l'historique git pour le détail de l'avancement.
