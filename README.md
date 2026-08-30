# Gestion Agence de Location de Voitures

Application desktop de gestion pour agence de location de voitures : clients, flotte, réservations, factures, tableau de bord.

## Stack

- Backend : Flask + SQLAlchemy (SQLite en dev, MySQL en production)
- Frontend : HTML / CSS / JavaScript (Alpine.js) + Chart.js
- Desktop : pywebview
- Tests : pytest

## Structure

```
backend/         API Flask, modèles, logique métier, tests
frontend/        Pages HTML, CSS, JS statiques
desktop/         Lanceur pywebview
license_server/  Serveur central de licences (activation, essai, suspension) — voir plus bas
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

Le résultat est dans `desktop/dist/AgenceLocation/` (mode `--onedir` : un dossier à distribuer, pas un seul fichier). Au premier lancement, l'app crée sa base de données, ses uploads et sa clé secrète dans un dossier de données utilisateur (`~/.local/share/AgenceLocation` sur Linux, `%APPDATA%\AgenceLocation` sur Windows, `~/Library/Application Support/AgenceLocation` sur Mac) — jamais dans le dossier d'installation, qui peut être en lecture seule. La fenêtre se lance sans console visible (`console=False`), avec l'icône `frontend/assets/logo/icon.ico`.

Le `.spec` a été écrit et testé sur Linux et Windows, et est conçu pour fonctionner tel quel sur Mac (imports cachés conditionnés par `sys.platform`). Un exécutable Windows ou Mac doit être **construit sur la plateforme cible respective** (limitation universelle de PyInstaller — impossible de cross-compiler).

### Installateur Windows (Inno Setup)

Pour distribuer une vraie installation Windows (raccourcis Menu Démarrer/Bureau, entrée de désinstallation dans "Applications et fonctionnalités") plutôt que le dossier brut `--onedir` :

```bash
# après avoir généré desktop/dist/AgenceLocation/ ci-dessus, et installé Inno Setup 6
iscc desktop/installer.iss
```

Produit `desktop/dist/AgenceLocationSetup.exe`. Installation par utilisateur (`PrivilegesRequired=lowest`), pas besoin de droits admin — cohérent avec le fait que les données vivent déjà dans `%APPDATA%\AgenceLocation`. Testé de bout en bout sur Windows (installation, raccourcis, désinstallation propre).

### Build automatique Windows / Mac / Linux via GitHub Actions

Le workflow `.github/workflows/build-desktop.yml` construit les trois exécutables en parallèle sur des runners GitHub (Windows, Mac, Linux), sans avoir besoin de ces machines soi-même :

1. Déclenchement manuel depuis l'onglet **Actions** du dépôt GitHub (bouton "Run workflow"), ou automatiquement en poussant un tag `v*` (ex: `v1.0.0`)
2. Chaque build est déposé comme **artifact** téléchargeable depuis la page du run (dossier `desktop/dist/AgenceLocation/` de l'OS correspondant ; pour Windows, un second artifact `AgenceLocation-windows-setup` contient l'installateur `AgenceLocationSetup.exe`)
3. Le build Windows (dossier et installateur) a été testé en pratique de bout en bout sur une vraie machine. Le build Mac reste à valider sur une vraie machine avant distribution — il lui manque aussi une icône `.icns` (voir commentaire dans `agence_location.spec`)

## Licence (essai 7 jours, approbation / blocage par installation)

L'exécutable packagé n'a aucune protection par lui-même : n'importe qui pourrait copier le dossier/l'installateur et l'utiliser gratuitement. `license_server/` corrige ça avec un petit serveur séparé, hébergé par l'éditeur (pas par le client), qui ne connaît que la liste des installations — jamais les données métier des agences (qui restent 100% locales chez chaque client).

**Fonctionnement côté client** : au **premier lancement, l'app s'enregistre automatiquement** auprès du serveur central (identifiant d'installation + empreinte machine hachée) et un **essai de 7 jours** démarre. Une connexion internet est requise à ce moment-là uniquement ; ensuite l'app fonctionne hors-ligne, avec un « heartbeat » périodique (toutes les 24 h, ou dès l'expiration de l'essai) pour détecter une approbation ou un blocage décidé par l'éditeur.

- **Essai en cours** : bandeau discret « X jours restants » (non bloquant).
- **Essai terminé** : 1 jour de grâce (bandeau rouge + coordonnées de contact), puis blocage automatique — sauf si l'éditeur a approuvé l'installation (paiement reçu → statut `actif`, illimité).
- **Blocage / réactivation manuels** : à tout moment depuis la console admin.
- Copier le dossier de l'app sur un autre poste crée une **nouvelle installation** visible (et blocable) dans la console. Supprimer le cache local ne relance pas l'essai : le serveur déduplique par empreinte machine.
- La date de référence est bornée par le dernier temps serveur connu : reculer l'horloge locale ne prolonge pas l'essai.

Le cache local vit dans le dossier de données utilisateur (`licence.json`, `licence.json.bak`, `install.dat`). Ce verrou n'est actif qu'en configuration `production` (l'exécutable packagé) : `flask run` en dev et la suite de tests ne sont jamais concernés.

**Lancer le serveur de licences en local :**

```bash
cd license_server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # définir ADMIN_TOKEN (openssl rand -hex 32) et DATABASE_URL
export FLASK_APP=wsgi.py
flask db upgrade               # crée la table installations
python wsgi.py                 # sert sur http://127.0.0.1:5100
```

Console d'administration (lister / approuver / bloquer / prolonger / éditer / supprimer les installations) sur `http://127.0.0.1:5100/admin`, protégée par le `ADMIN_TOKEN`.

**En production** : le serveur est déployé sur une VM (Oracle Cloud Free Tier) derrière nginx + HTTPS, service `systemd` + gunicorn, sauvegarde SQLite quotidienne. L'app cliente pointe vers `https://<domaine>` via le défaut `LICENCE_SERVER_URL` de `ProductionConfig` (surchargeable par variable d'environnement).

## État du projet

En cours de développement, module par module. Voir l'historique git pour le détail de l'avancement.
