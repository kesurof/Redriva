# 🚀 Redriva - Gestionnaire Real-Debrid Avancé

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Validated-green?logo=security)](DEPLOYMENT_REPORT.md)

# 🚀 Redriva - Gestionnaire Real-Debrid Simplifié

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://python.org)
[![SSDV2](https://img.shields.io/badge/SSDV2-Compatible-orange)](https://github.com/projetssd/ssdv2)

> **Interface web simple et efficace pour Real-Debrid avec support SSDV2**

## ✨ Fonctionnalités

- 📥 **Gestion des téléchargements Real-Debrid**
- 🔄 **Synchronisation automatique**
- 📊 **Interface web moderne**
- 🔗 **Gestion des symlinks**
- 🐳 **Compatible Docker & SSDV2**

---

## 🚀 Installation

### Mode Développement/Local

```bash
# 1. Clone
git clone https://github.com/kesurof/redriva.git
cd redriva

# 2. Configuration du token
echo "VOTRE_TOKEN_RD" > data/token

# 3. Démarrage
python src/web.py
```

### Mode Docker

```bash
# Option 1: Variables d'environnement (recommandé)
docker run -p 5000:5000 \
  -e RD_TOKEN="votre_token_real_debrid" \
  -e SONARR_URL="http://localhost:8989" \
  -e SONARR_API_KEY="votre_clé_sonarr" \
  -e RADARR_URL="http://localhost:7878" \
  -e RADARR_API_KEY="votre_clé_radarr" \
  ghcr.io/kesurof/redriva:ssdv2

# Option 2: Docker Compose
docker-compose up -d
```

### Mode SSDV2

```bash
# 1. Setup initial
./ssdv2-setup.sh

# 2. Configuration token

# 3. Déploiement via SSDV2
# Ajoutez redriva à votre configuration SSDV2
```

---

## 🔧 Configuration

### Variables d'environnement (Docker/SSDV2)
- `RD_TOKEN` : Token Real-Debrid (obligatoire)
- `SONARR_URL` : URL de Sonarr (optionnel)
- `SONARR_API_KEY` : Clé API Sonarr (optionnel)
- `RADARR_URL` : URL de Radarr (optionnel)
- `RADARR_API_KEY` : Clé API Radarr (optionnel)
- `PUID/PGID` : ID utilisateur (SSDV2)
- `TZ` : Fuseau horaire

### Fichiers locaux (Développement)
- `data/token` : Token Real-Debrid
- `config/config.json` : Configuration générale

---

## 📁 Structure Simplifiée

```
redriva/
├── src/
│   ├── web.py              # Application Flask
│   ├── main.py             # Logique Real-Debrid
│   ├── config_manager.py   # Configuration
│   └── templates/          # Interface web
├── config/
│   └── config.json         # Configuration
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Compose local
└── ssdv2-setup.sh         # Setup SSDV2
```

---

## 🌐 Accès

- **Local** : http://localhost:5000
- **Docker** : http://localhost:5000
- **SSDV2** : https://redriva.votre-domaine.com

---

## 📖 Documentation

- **Configuration** : Interface web > Paramètres
- **API Health** : `/api/health`
- **Logs** : `docker logs redriva`

---

## 🎯 Prochaines Étapes

1. **Configurez votre token Real-Debrid**
2. **Accédez à l'interface web**
3. **Configurez vos paramètres**
4. **Profitez !**

## ✨ Fonctionnalités Principales

### 🎯 Gestion des Téléchargements
- � **Interface web intuitive** - Gestion complète de vos téléchargements Real-Debrid
- 🔄 **Synchronisation automatique** - Import et suivi des torrents
- � **Tableau de bord** - Vue d'ensemble avec statistiques en temps réel
- 🔍 **Recherche avancée** - Filtrage et recherche dans vos téléchargements
- � **Mode sombre** - Interface moderne et responsive

### 🔗 Intégration Sonarr/Radarr
- � **Sonarr** - Gestion automatique des séries TV
- � **Radarr** - Gestion automatique des films
- � **Symlinks automatiques** - Création de liens symboliques vers vos médias
- ⚙️ **Configuration centralisée** - Paramètres unifiés dans l'interface web

### 🛡️ Sécurité et Configuration
- 🔧 **Configuration centralisée** - Système JSON unifié avec templates
- 🔐 **Sécurité Docker avancée** - Conteneurs non-root, volumes read-only
- 🌐 **Support proxy reverse** - Traefik, Nginx, Apache
- 📁 **Gestion automatique des chemins** - Adaptation Docker/développement

### 📊 Monitoring et Maintenance
- 💚 **Healthcheck intégré** - Surveillance automatique de l'état
- 📝 **Logs structurés** - Debugging et monitoring facilités
- 🔄 **Déploiement automatisé** - Scripts de déploiement complets
- 📋 **Validation automatique** - Tests de configuration et persistance

## 🛠️ Installation

### Développement (Python)

Pour développer et tester localement :

```bash
# 1. Cloner le projet
git clone https://github.com/kesurof/Redriva.git
cd Redriva

# 2. Configuration initiale
./setup.sh

# 3. Configurer votre token Real-Debrid
# Option A: Via fichier de configuration (recommandé)
cp config/conf.example.json config/conf.json
nano config/conf.json
# Modifiez la section "tokens" > "real_debrid"

# Option B: Via variable d'environnement
# Remplacez 'votre_token_ici' par votre vrai token

# 4. Lancer en mode développement
./dev.sh
```

L'application sera accessible sur `http://localhost:5000` 🎉

### Production (Docker)

Pour déployer en production :

```bash
# 1. Cloner le projet
git clone https://github.com/kesurof/Redriva.git
cd Redriva

# 2. Configuration initiale
./setup.sh

# 3. Configurer votre token Real-Debrid
# Option A: Via fichier de configuration
cp config/conf.example.json config/conf.json
nano config/conf.json
# Modifiez la section "tokens" > "real_debrid"

# Option B: Via variable d'environnement Docker
# Remplacez 'votre_token_ici' par votre vrai token

# 4. Lancer avec Docker
docker-compose up -d

# Commandes utiles
docker-compose logs -f    # Voir les logs
docker-compose down       # Arrêter
docker-compose pull       # Mettre à jour
```

L'image Docker est automatiquement construite et disponible sur `ghcr.io/kesurof/redriva:latest`.

## ⚙️ Configuration

### 🔧 Configuration centralisée

Redriva utilise maintenant un système de configuration centralisé basé sur le fichier `config/conf.json`. Ce fichier unifie tous les paramètres de l'application :

```json
{
  "tokens": {
    "real_debrid": "VOTRE_TOKEN_ICI"
  },
  "sonarr": {
    "enabled": true,
    "url": "http://localhost:8989",
    "api_key": "VOTRE_CLE_API_SONARR"
  },
  "radarr": {
    "enabled": false,
    "url": "http://localhost:7878", 
    "api_key": "VOTRE_CLE_API_RADARR"
  },
  "paths": {
    "media": "/app/medias",
    "media_dev": "/home/user/Medias/"
  }
}
```

### 🔑 Token Real-Debrid

1. Connectez-vous sur [Real-Debrid](https://real-debrid.com)
2. Allez dans **Mon compte** → **Clé API**
3. Copiez votre token
4. **Option A** - Configuration centralisée (recommandé) :
   ```bash
   nano config/conf.json
   # Modifiez "tokens" > "real_debrid"
   ```
5. **Option B** - Variable d'environnement :
   ```bash
   # Modifiez RD_TOKEN=votre_token_ici
   ```

### � Configuration Sonarr/Radarr

Pour l'intégration avec vos services *Arr :

1. **Via l'interface web** : Allez dans Paramètres → *Arrs
2. **Via le fichier de configuration** :
   ```json
   {
     "sonarr": {
       "enabled": true,
       "url": "http://localhost:8989",
       "api_key": "votre_cle_api_sonarr"
     },
     "radarr": {
       "enabled": true,
       "url": "http://localhost:7878",
       "api_key": "votre_cle_api_radarr"
     }
   }
   ```

### 🔗 Symlink Manager

Le gestionnaire de liens symboliques utilise automatiquement la configuration Sonarr/Radarr définie dans `conf.json`. Configurez vos services *Arr une seule fois et ils seront disponibles partout !

### 🌍 Détection d'environnement

Redriva détecte automatiquement votre environnement :
- **Docker** : Utilise les chemins `/app/*`
- **Développement local** : Utilise les chemins relatifs `./data/*`
- **Personnalisé** : Configurez `paths.media_dev` pour le développement

## �📖 Utilisation

1. **Ajout de torrents/magnets** : Collez vos liens dans l'interface
2. **Navigation** : Parcourez vos fichiers par dossiers
3. **Téléchargement** : Clic droit → "Enregistrer sous" ou clic direct
4. **Gestion** : Organisez et supprimez vos téléchargements
5. **Symlinks** : Créez automatiquement des liens vers vos médias
6. **Configuration** : Gérez tous vos paramètres depuis l'interface web

## 🔄 Migration depuis l'ancienne version

Si vous utilisez une version antérieure de Redriva :

1. **Migration automatique** : Au premier démarrage, Redriva migre automatiquement votre configuration depuis `data/settings.json`
2. **Vérification** : Exécutez `python test_config.py` pour valider la migration
3. **Sauvegarde** : Vos anciens fichiers sont conservés comme sauvegarde

## 🏗️ Architecture

- **Backend** : Python Flask avec Real-Debrid API
- **Frontend** : HTML/CSS/JavaScript moderne
- **Base de données** : SQLite pour la synchronisation
- **Configuration** : JSON centralisé avec détection d'environnement
- **Déploiement** : Docker avec GitHub Actions CI/CD

## 🧪 Tests et validation

Pour valider votre installation :

```bash
# Test de la configuration
python test_config.py

# Vérification des modules
python -c "import src.config_manager; print('✅ Configuration OK')"

# Test de l'interface web
python src/web.py
# Ouvrez http://localhost:5000
```

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [Real-Debrid](https://real-debrid.com) pour leur excellente API
- La communauté open source pour l'inspiration

---

## 🚀 Déploiement SSDV2

### Installation automatique

```bash
# Installation dans SSDV2
git clone https://github.com/kesurof/redriva.git
cd redriva
./install-ssdv2.sh

# Configuration du token
# Modifier: RD_TOKEN=votre_token_real_debrid

# Déploiement avec Ansible
cd /opt/seedbox
ansible-playbook site.yml -t redriva
```

### Configuration manuelle

1. **Fichiers de configuration SSDV2** (voir documentation projetssd)
  - `pretask.yml` - Création des répertoires (configuration via interface web)
   - `posttask.yml` - Vérification santé et configuration token
   - `redriva.yml` - Configuration Docker avec volumes SSDV2

2. **Variables d'environnement importantes**
   ```bash
   RD_TOKEN=votre_token_real_debrid  # Obligatoire
   PUID=1000                        # Auto-géré par SSDV2
   PGID=1000                        # Auto-géré par SSDV2  
   TZ=Europe/Paris                  # Fuseau horaire
   ```

3. **Volumes SSDV2 intégrés**
   - `/zurg/data/info` - Informations Zurg (lecture seule)
   - `/app/medias` - Répertoire média principal
   - `/home/USER` - Répertoire utilisateur
   - Docker socket pour gestion containers

### Interface Web

- **URL**: `https://redriva.votre-domaine.com` (géré par Traefik/SSDV2)
- **Healthcheck**: `http://localhost:5000/api/health`
- **Logs**: `docker logs redriva`

---

**⚡ Redriva - Votre passerelle vers Real-Debrid !**
