# Guide Docker pour Redriva

## 🐳 Configuration Docker

### Prérequis
- Docker installé (version 20.10+)
- Docker Compose installé (version 2.x)
- Token Real-Debrid valide

### 🚀 Installation Rapide (Recommandée)

Utilisez l'assistant Docker pour une configuration automatisée :

1. **Clonez le repository**
   ```bash
   git clone https://github.com/kesurof/Redriva.git
   cd Redriva
   ```

2. **Configuration automatique**
   ```bash
   ./docker-helper.sh setup
   ```
   
3. **Modifiez votre token**
   Éditez `config/.env` et remplacez `votre_token_ici` par votre token Real-Debrid.

4. **Démarrez Redriva**
   ```bash
   ./docker-helper.sh start
   ```

L'application sera accessible sur `http://localhost:5000`

### 📋 Commandes de l'Assistant Docker

| Commande | Description |
|----------|-------------|
| `./docker-helper.sh setup` | Configuration initiale complète |
| `./docker-helper.sh start` | Démarre les conteneurs |
| `./docker-helper.sh stop` | Arrête les conteneurs |
| `./docker-helper.sh restart` | Redémarre les conteneurs |
| `./docker-helper.sh logs` | Affiche les logs en temps réel |
| `./docker-helper.sh status` | Vérifie l'état des conteneurs |
| `./docker-helper.sh update` | Met à jour vers la dernière version |
| `./docker-helper.sh shell` | Accès shell dans le conteneur |
| `./docker-helper.sh clean` | Nettoie les images inutilisées |

### Installation manuelle

Si vous préférez configurer manuellement :

1. **Configuration initiale**
   ```bash
   ./setup.sh
   ```
   Puis éditez `config/.env` avec votre token Real-Debrid.

2. **Lancement avec Docker Compose**
   ```bash
   docker-compose up -d
   ```

### 🔧 Construction manuelle de l'image

```bash
# Construction avec le script
./build_docker.sh

# Ou manuellement
docker build -t kesurof/redriva:latest .

# Test de l'image
docker run --rm kesurof/redriva:latest python -c "import src.main; print('OK')"
```

### ⚙️ Configuration avancée

#### Variables d'environnement disponibles

| Variable | Description | Défaut |
|----------|-------------|---------|
| `RD_TOKEN` | Token Real-Debrid (obligatoire) | - |
| `FLASK_HOST` | Interface d'écoute | `0.0.0.0` |
| `FLASK_PORT` | Port d'écoute | `5000` |
| `FLASK_DEBUG` | Mode debug Flask | `false` |
| `RD_MAX_CONCURRENT` | Requêtes simultanées | `50` |
| `RD_BATCH_SIZE` | Taille des batches | `250` |
| `RD_QUOTA_WAIT` | Attente quota global (sec) | `60` |
| `RD_TORRENT_WAIT` | Attente quota torrent (sec) | `10` |
| `GUNICORN_WORKERS` | Nombre de workers Gunicorn | `2` |
| `GUNICORN_TIMEOUT` | Timeout Gunicorn (sec) | `120` |
| `GUNICORN_KEEPALIVE` | Keep-alive Gunicorn (sec) | `5` |

#### Variables Symlink Manager

| Variable | Description | Défaut |
|----------|-------------|---------|
| `REDRIVA_MEDIA_PATH` | Chemin vers les médias | `/app/medias` |
| `REDRIVA_WORKERS` | Workers pour les scans | `4` |
| `REDRIVA_DB_PATH` | Chemin base de données | `/app/data/redriva.db` |

#### Volumes Docker

- `./data:/app/data` - Base de données SQLite et données persistantes
- `./config:/app/config` - Fichiers de configuration (.env)
- `./medias:/app/medias` - Répertoire des médias pour Symlink Manager

#### Health Check

Le conteneur inclut un health check automatique qui vérifie :
- Que l'application répond sur `/api/health`
- Toutes les 30 secondes
- Timeout de 10 secondes
- 3 tentatives avant de marquer comme unhealthy

### 📋 Commandes Docker Natives

```bash
# Voir les logs
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs -f redriva

# Redémarrer le service
docker-compose restart

# Arrêter le service
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Mise à jour de l'image
docker-compose pull && docker-compose up -d

# Accès au shell du conteneur
docker-compose exec redriva bash

# Exécuter des commandes Redriva
docker-compose exec redriva python src/main.py --stats
docker-compose exec redriva python src/main.py --sync-smart

# Voir l'état des conteneurs
docker-compose ps

# Voir la santé des conteneurs
docker ps --filter "name=redriva"
```

### 🔍 Vérification de l'installation

Pour vérifier que votre configuration Docker est correcte :

```bash
# Script de vérification automatique
./docker-check.sh
```

Ce script vérifie :
- ✅ Présence et fonctionnement de Docker/Docker Compose
- ✅ Présence de tous les fichiers requis
- ✅ Validité de la configuration docker-compose.yml
- ✅ Configuration du token Real-Debrid
- ✅ Permissions des scripts
- 🔧 Option de test de construction d'image

### 🩺 Résolution de problèmes

#### Port déjà utilisé
```bash
# Changer le port dans docker-compose.yml
ports:
  - "8080:5000"  # Utilise le port 8080 au lieu de 5000
```

#### Problèmes de permissions
```bash
# Vérifier les permissions des dossiers
sudo chown -R $(id -u):$(id -g) data/ config/

# Ou recréer les dossiers
rm -rf data/ config/
./docker-helper.sh setup
```

#### Token Real-Debrid non configuré
```bash
# Vérifier la configuration
cat config/.env | grep RD_TOKEN

# Reconfigurer si nécessaire
./docker-helper.sh setup
nano config/.env
```

#### Conteneur en état "unhealthy"
```bash
# Vérifier les logs
docker-compose logs redriva

# Vérifier le health check
docker inspect redriva_web | grep -A 10 Health

# Redémarrer en cas de problème
docker-compose restart
```

#### Logs détaillés
```bash
# Activer le mode debug
echo "FLASK_DEBUG=true" >> config/.env
docker-compose restart

# Voir tous les logs système
docker-compose logs -f --tail=100
```

#### Problèmes de réseau
```bash
# Vérifier que l'application répond
curl http://localhost:5000/api/health

# Tester depuis l'intérieur du conteneur
docker-compose exec redriva wget -qO- http://localhost:5000/api/health
```

### 🔒 Sécurité

- ✅ Token Real-Debrid n'est jamais inclus dans l'image Docker
- ✅ Configuration via fichier `.env` local uniquement
- ✅ Exécution en utilisateur non-root dans le conteneur
- ✅ Isolation des données via volumes Docker
- ✅ Health checks automatiques
- ✅ Logs d'accès et d'erreur activés

### 📚 Support et contribution

- 🐛 Issues: https://github.com/kesurof/Redriva/issues
- 📖 Documentation: README.md
- 🔧 Scripts d'aide: `./docker-helper.sh help`
- ⚖️ License: Voir fichier LICENSE
