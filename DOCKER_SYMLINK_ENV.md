# 🔧 Variables d'environnement Docker pour Symlink Manager

## 📋 Variables disponibles

Le Symlink Manager utilise plusieurs variables d'environnement pour s'adapter aux différents environnements Docker :

### Variables principales

| Variable | Description | Valeur par défaut | Exemple |
|----------|-------------|-------------------|---------|
| `REDRIVA_MEDIA_PATH` | Chemin vers le répertoire des médias | `/app/medias` | `/mnt/medias` |
| `REDRIVA_DB_PATH` | Chemin vers la base de données SQLite | `/app/data/redriva.db` | `/app/data/redriva.db` |
| `REDRIVA_WORKERS` | Nombre de workers pour les scans | `4` | `8` |

## 🐳 Configuration Docker Compose

### Exemple 1 : Configuration standard
```yaml
services:
  redriva:
    image: ghcr.io/kesurof/redriva:latest
    container_name: redriva
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config  
      - ./medias:/app/medias:rw  # Chemin par défaut
    environment:
      # Variables Symlink Manager (optionnelles)
      - REDRIVA_MEDIA_PATH=/app/medias
      - REDRIVA_WORKERS=4
    env_file:
      - ./config/.env
```

### Exemple 2 : Chemin personnalisé
```yaml
services:
  redriva:
    image: ghcr.io/kesurof/redriva:latest
    container_name: redriva
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config  
      - /mnt/storage/medias:/mnt/medias:rw  # Chemin personnalisé
    environment:
      # Configuration personnalisée
      - REDRIVA_MEDIA_PATH=/mnt/medias
      - REDRIVA_WORKERS=8
    env_file:
      - ./config/.env
```

### Exemple 3 : Multiples volumes de médias
```yaml
services:
  redriva:
    image: ghcr.io/kesurof/redriva:latest
    container_name: redriva
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config  
      - /mnt/disk1/movies:/app/movies:rw
      - /mnt/disk2/series:/app/series:rw
      - /mnt/disk3/downloads:/app/downloads:rw
    environment:
      # Le symlink manager scannera le répertoire parent
      - REDRIVA_MEDIA_PATH=/app
      - REDRIVA_WORKERS=6
    env_file:
      - ./config/.env
```

## 🛠️ Configuration via fichier .env

Vous pouvez aussi ajouter ces variables dans votre fichier `config/.env` :

```bash
# Real-Debrid (obligatoire)
RD_TOKEN=votre_token_real_debrid

# Symlink Manager (optionnel)
REDRIVA_MEDIA_PATH=/app/medias
REDRIVA_WORKERS=4
REDRIVA_DB_PATH=/app/data/redriva.db

# Autres variables Flask/Gunicorn
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

## 🗂️ Structure recommandée

### Structure simple
```
projet/
├── docker-compose.yml
├── config/
│   └── .env
├── data/
│   └── redriva.db
└── medias/          # ← REDRIVA_MEDIA_PATH pointe ici
    ├── movies/
    ├── series/
    └── downloads/
```

### Structure avancée avec NAS
```
/mnt/nas/
├── movies/          # Films
├── series/          # Séries
├── music/           # Musique
└── downloads/       # Téléchargements

# Dans docker-compose.yml :
# - /mnt/nas:/app/nas:rw
# REDRIVA_MEDIA_PATH=/app/nas
```

## 🔍 Vérification de la configuration

Pour vérifier que vos variables sont bien prises en compte :

1. **Démarrez le conteneur**
   ```bash
   docker-compose up -d
   ```

2. **Vérifiez les logs**
   ```bash
   docker-compose logs redriva | grep -i symlink
   ```

3. **Testez dans l'interface web**
   - Allez sur `http://localhost:5000/symlink`
   - Onglet "Settings" → Le chemin des médias doit afficher votre variable
   - Onglet "Scanner" → Cliquez sur "Charger les répertoires"

## ⚠️ Notes importantes

1. **Permissions** : Assurez-vous que le conteneur a les bonnes permissions sur les volumes montés
   ```bash
   sudo chown -R 1000:1000 ./medias/
   ```

2. **Chemins absolus** : Utilisez toujours des chemins absolus dans les variables d'environnement

3. **Répertoires existants** : Les répertoires doivent exister sur l'hôte avant le montage

4. **Modifications** : Après modification des variables, redémarrez le conteneur
   ```bash
   docker-compose restart
   ```

## 🐛 Dépannage

### Le scanner ne trouve pas les répertoires
- Vérifiez que `REDRIVA_MEDIA_PATH` correspond au point de montage dans le conteneur
- Vérifiez les permissions des répertoires
- Consultez les logs : `docker-compose logs redriva`

### Configuration non prise en compte
- Redémarrez le conteneur après modification des variables
- Vérifiez que les variables sont bien définies : `docker-compose config`

### Erreur de base de données
- Vérifiez que `REDRIVA_DB_PATH` pointe vers un répertoire accessible en écriture
- Le répertoire parent doit exister et être monté

## 📚 Ressources

- [Guide Docker principal](DOCKER.md)
- [Documentation Symlink Integration](SYMLINK_INTEGRATION.md)
- [Configuration avancée](README.md)
