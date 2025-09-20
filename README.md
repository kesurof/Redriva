# Redriva — Gestionnaire Real‑Debrid (SSDV2 & développement)

Un petit service web pour gérer et synchroniser vos téléchargements Real‑Debrid.
Ce dépôt contient une application Python (Flask) légère, prête à être déployée en
mode local (venv), en conteneur Docker ou intégrée dans SSDV2.

## Points clés

- Backend : Python 3.11+ (Flask)
- Base de données : SQLite (fichier local dans `./data`)
- Virtualenv de développement : `./redriva/` (généré par `./dev.sh`)
- Entrée application : `src/web.py`
- Script d'aide local : `./dev.sh` (démarrage foreground / background)
- Docker : `Dockerfile` + `docker-compose.yml`
- SSDV2 : configuration de déploiement dans `ssdv2/redriva.yml`

## Table des matières

- Présentation
- Installation rapide
  - SSDV2
  - Docker Compose
  - Développement local
- Configuration
  - Token Real‑Debrid
  - Sonarr / Radarr
- Utilisation
  - Commandes `dev.sh`
  - Vérifications et logs
- Fichiers importants
- Dépannage rapide
- Contribution
- Licence

## Présentation

Redriva centralise et synchronise vos torrents/URLs Real‑Debrid dans une base
SQLite locale et expose une interface web simple pour consulter et gérer
les éléments synchronisés. Le projet inclut des intégrations optionnelles pour
Sonarr et Radarr, et un gestionnaire de symlinks.

Le dépôt est pensé pour être utilisé :
- en local via un virtualenv isolé (script `dev.sh`),
- en Docker (image `ghcr.io/kesurof/redriva:ssdv2` ou build local),
- intégré dans SSDV2 via `ssdv2/redriva.yml`.

## Installation et déploiement

Remarque : les instructions ci‑dessous partent du principe que vous avez cloné
le dépôt et que vous êtes à la racine du projet.

```bash
git clone https://github.com/kesurof/Redriva.git
cd Redriva
```

### 1) Déploiement SSDV2 (recommandé pour seedboxes)

Ce projet contient un fichier `ssdv2/redriva.yml` prêt à être inclus dans
votre configuration SSDV2. Les points importants :

- Image Docker recommandée : `ghcr.io/kesurof/redriva:ssdv2`
- Ports : 5000 (interne) -> mappez selon votre configuration SSDV2
- Volumes recommandés (extrait) :
  - `/app/config` → configuration (mappez vers `{{ settings.storage }}/.../config`)
  - `/app/data` → données SQLite et tokens
  - `/app/medias` → répertoire média (optionnel)
  - `/var/run/docker.sock` en lecture seule (optionnel)
  - `/etc/localtime:/etc/localtime:ro`
- Variables d'environnement utiles : `PUID`, `PGID`, `TZ`, `RD_TOKEN`, `SONARR_URL`, `SONARR_API_KEY`, `RADARR_URL`, `RADARR_API_KEY`

Procédure générale :
1. Ajoutez `ssdv2/redriva.yml` à votre configuration SSDV2.
2. Définissez les variables (PUID/PGID/TZ) et, si souhaité, `RD_TOKEN`.
3. Déployez via SSDV2 (Ansible / playbook fourni par votre infra).

Note : SSDV2 peut gérer automatiquement les tokens et secrets via son système
de variables — privilégiez cette méthode plutôt que d'insérer des tokens en clair.

### 2) Docker Compose (local)

1. Construisez et lancez le service :

```bash
docker-compose up -d
```

2. Par défaut, le service expose le port `5000`.
3. Les volumes montés localement sont : `./data` (données), `./config` (config).

Astuce : pour le développement rapide, vous pouvez décommenter ou ajouter un
service `redriva-dev` dans `docker-compose.yml` pour monter `./src` en lecture
écrite et activer `FLASK_DEBUG=1`.

### 3) Développement local (venv isolé)

Le script `dev.sh` automatise la création d'un virtualenv local `./redriva/`,
installe les dépendances depuis `requirements.txt` et démarre l'application.

Commandes utiles :

- Démarrer au premier plan (debug) :

```bash
./dev.sh start-foreground
```

- Démarrer en arrière‑plan (logs -> `logs/dev.log`) :

```bash
./dev.sh start-bg
```

- Arrêter l'instance background :

```bash
./dev.sh stop
```

- Redémarrer :

```bash
./dev.sh restart
```

- Statut (vérifie PID enregistré) :

```bash
./dev.sh status
```

Options :
- `--recreate-venv` ou `-r` : recrée le venv avant d'installer les dépendances.
- `-h` / `--help` : affiche l'aide du script.

Remarques techniques :
- Le script lance Python dans un environnement nettoyé (`env -i`) pour éviter
  les interférences avec d'autres venvs.
- Le PID de l'instance background est stocké dans `./.run/redriva.pid`.
- Les logs sont écrits dans `./logs/dev.log` et `./logs/dev.err.log`.

## Configuration

Le projet supporte deux modes de configuration :

1. Variables d'environnement (pratique en Docker/SSDV2) :
   - RD_TOKEN : token Real‑Debrid (recommandé éviter l'exposition en clair)
   - SONARR_URL, SONARR_API_KEY
   - RADARR_URL, RADARR_API_KEY
   - PUID, PGID, TZ

2. Fichiers locaux (développement) :
   - `data/token` : token Real‑Debrid (si présent, utilisé en priorité en dev)
   - `config/config.json` (ou `config/conf.json` selon version) : configuration centralisée

Important : protégez `data/token` et `config/conf.json` — le dépôt `.gitignore`
exclut ces fichiers pour éviter d'exposer vos secrets.

## Utilisation

- Accès web local : http://localhost:5000
- Endpoint healthcheck : `/api/health`

Fonctionnalités exposées par l'interface :
- Visualiser la liste des torrents synchronisés
- Lancer manuellement un cycle Arr (Sonarr/Radarr)
- Gérer les symlinks (si `symlink_tool` disponible)
- Consulter les logs et statistiques

## Fichiers importants

- `src/web.py` : point d'entrée Flask (application)
- `src/main.py` : logique métier (synchronisation Real‑Debrid)
- `src/config_manager.py` : gestion de la configuration
- `src/symlink_tool.py` : création & gestion des symlinks (optionnel)
- `dev.sh` : script de développement (venv, start/stop)
- `docker-compose.yml`, `Dockerfile` : déploiement Docker
- `ssdv2/redriva.yml` : configuration SSDV2
- `data/` : données runtime (token, DB)
- `logs/` : logs de développement

## Dépannage rapide

- L'application ne démarre pas :
  - Vérifiez `logs/dev.err.log` et `logs/dev.log`.
  - Si en background, vérifiez `./.run/redriva.pid` et utilisez `./dev.sh status`.
  - Assurez‑vous que le token RD est fourni (variable d'env `RD_TOKEN` ou `data/token`).

- Erreur de dépendances :
  - Supprimez `redriva/` puis lancez `./dev.sh -r start-foreground`.

- Problèmes SSDV2 :
  - Vérifiez vos variables `PUID`/`PGID` et les chemins montés dans `redriva.yml`.

## Contribution

Les contributions sont bienvenues :

1. Fork du projet
2. Créer une branche : `git checkout -b feature/ma-fonctionnalite`
3. Commit & push
4. Ouvrir une Pull Request

Veuillez garder les tokens et fichiers sensibles hors des commits.

## Licence

Ce projet est distribué sous licence MIT — voir le fichier `LICENSE`.

---

Si vous voulez, je peux :
- ajouter des exemples de `config/conf.json` ou `data/token` à inclure dans le README,
- créer un fichier `docs/SSDV2.md` détaillant l'intégration Ansible/SSDV2,
- générer une version anglaise.

Dites-moi ce que vous préférez comme suite.
