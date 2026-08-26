# Gestion Agence de Location de Voitures

Application desktop de gestion pour agence de location de voitures : clients, flotte, réservations, factures, tableau de bord.

## Stack

- Backend : Flask + SQLAlchemy (SQLite en dev, MySQL en production)
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

## Base de données MySQL

Par défaut l'app utilise SQLite (`backend/instance/app.db`), pratique pour développer sans rien installer. Pour la production, elle bascule sur MySQL simplement en changeant `DATABASE_URL` — aucun autre changement de code n'est nécessaire.

1. Installer MySQL Server et créer une base vide :

   ```sql
   CREATE DATABASE agence_location CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'agence_location'@'localhost' IDENTIFIED BY 'un-mot-de-passe-fort';
   GRANT ALL PRIVILEGES ON agence_location.* TO 'agence_location'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. Dans `backend/.env`, remplacer `DATABASE_URL` par :

   ```
   DATABASE_URL=mysql+pymysql://agence_location:un-mot-de-passe-fort@127.0.0.1:3306/agence_location
   ```

3. Appliquer les migrations sur la nouvelle base :

   ```bash
   cd backend
   flask db upgrade
   flask create-admin
   ```

Le driver `PyMySQL` est déjà dans `backend/requirements.txt`.

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
