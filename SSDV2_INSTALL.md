# 🚀 Redriva SSDV2 - Installation Guide

## 📦 Image Docker Officielle
```
kesurof/redriva:ssdv2
```

## 🔧 Installation Automatique

### 1. Clone du projet
```bash
git clone https://github.com/kesurof/Redriva.git /tmp/redriva
cd /tmp/redriva
```

### 2. Setup SSDV2
```bash
./ssdv2-setup.sh
```

### 3. Configuration
```bash
cd /opt/seedbox/docker/$USER/redriva
nano .env
```

Configurez vos variables :
```env
RD_TOKEN=your_real_debrid_token_here
PUID=1000
PGID=1000
TZ=Europe/Paris
DOMAIN=your_domain.com
```

### 4. Démarrage
```bash
docker-compose up -d
```

## 🐳 Configuration Docker Compose

Le fichier `docker-compose.yml` est automatiquement créé avec :

- **Image**: `kesurof/redriva:ssdv2`
- **Port**: 5000
- **Volumes**: Persistance des données
- **Labels**: Compatible SSDV2 + Traefik
- **Healthcheck**: Monitoring automatique

## 🌐 Accès Web

- **Local**: `http://localhost:5000`
- **SSDV2**: `https://redriva.your_domain.com`

## 📋 Commandes Utiles

```bash
# Vérifier les logs
docker-compose logs -f redriva

# Redémarrer le service
docker-compose restart redriva

# Mise à jour de l'image
docker-compose pull && docker-compose up -d

# Arrêt du service
docker-compose down
```

## 🔑 Configuration Real-Debrid

1. Connectez-vous à [Real-Debrid](https://real-debrid.com)
2. Allez dans **Mon compte** → **API**
3. Copiez votre **Token API**
4. Ajoutez-le dans le fichier `.env`

## 📁 Structure des Volumes

```
/opt/seedbox/docker/$USER/redriva/
├── .env                    # Variables d'environnement
├── docker-compose.yml      # Configuration Docker
├── data/                   # Base de données SQLite
│   └── redriva.db
└── medias/                 # Fichiers téléchargés
```

## 🚨 Dépannage

### Container ne démarre pas
```bash
docker-compose logs redriva
```

### Port déjà utilisé
Modifiez le port dans `docker-compose.yml` :
```yaml
ports:
  - "5001:5000"  # Utilisez 5001 au lieu de 5000
```

### Token Real-Debrid invalide
Vérifiez et régénérez votre token API sur real-debrid.com

## 🔄 Mise à jour

```bash
cd /opt/seedbox/docker/$USER/redriva
docker-compose pull
docker-compose up -d
```

L'image `kesurof/redriva:ssdv2` est automatiquement mise à jour depuis la branche `alpha` du repository GitHub.

## 📞 Support

- **GitHub Issues**: [Redriva Issues](https://github.com/kesurof/Redriva/issues)
- **Documentation**: [README principal](https://github.com/kesurof/Redriva)

---

**Image Docker**: `kesurof/redriva:ssdv2` | **Branche**: `alpha` | **Compatibilité**: SSDV2 ✅
