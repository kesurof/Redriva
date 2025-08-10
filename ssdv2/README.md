# 🚀 SSDV2 Integration Files

Ce dossier contient tous les fichiers nécessaires pour l'intégration de Redriva dans SSDV2.

## 📁 Structure

```
ssdv2/
├── redriva.yml           # Configuration principale SSDV2
├── pretask.yml          # Tâches de pré-installation
├── posttask.yml         # Tâches de post-installation
├── docker-compose.yml   # Docker Compose pour SSDV2
└── README.md           # Cette documentation
```

## 🔧 Installation dans SSDV2

### 1. Copie des fichiers
```bash
# Copier les fichiers dans le dossier SSDV2 approprié
cp ssdv2/* /opt/seedbox/docker/apps/redriva/
```

### 2. Configuration Ansible
Les fichiers sont prêts à être utilisés par le système Ansible de SSDV2 :

- **`redriva.yml`** : Configuration principale avec volumes et environnement
- **`pretask.yml`** : Création des répertoires et fichiers de configuration
- **`posttask.yml`** : Configuration interactive du token et vérifications

### 3. Image Docker
L'application utilise l'image officielle :
```
ghcr.io/kesurof/redriva:ssdv2
```

## 🎯 Fonctionnalités SSDV2

### Intégrations automatiques
- ✅ **Zurg** : Lecture des infos torrents depuis `/zurg/data/info`
- ✅ **Medias** : Accès aux médias via `~/Medias`
- ✅ **Docker** : Communication avec Docker daemon
- ✅ **Traefik** : Reverse proxy automatique

### Configuration interactive
- 🔑 **Token Real-Debrid** : Demande interactive lors de l'installation
- 📁 **Répertoires** : Création automatique avec bonnes permissions
- ⚡ **Health checks** : Vérification du bon fonctionnement

### Variables d'environnement
```yaml
PUID: "{{ lookup('env','MYUID') }}"
PGID: "{{ lookup('env','MYGID') }}"
TZ: "{{ lookup('env','TZ') }}"
```

## 🔧 Personnalisation

### Modifier les volumes
Éditez `redriva.yml` section `pg_volumes` :
```yaml
pg_volumes:
  - "{{ settings.storage }}/docker/{{ lookup('env','USER') }}/{{ pgrole }}/config:/app/config:rw"
  # Ajoutez vos volumes personnalisés ici
```

### Modifier les variables d'environnement
Éditez `pretask.yml` section `.env.example` :
```yaml
content: |
  # Configuration Redriva
  RD_TOKEN=your_real_debrid_token_here
  # Ajoutez vos variables ici
```

## ✅ Avantages de cette approche

- 🎯 **Séparation claire** : SSDV2 et développement local séparés
- 🔄 **Maintenance facile** : Mise à jour indépendante des fichiers
- 🚀 **Installation automatisée** : Tout géré par Ansible
- 🔧 **Configuration interactive** : Token demandé à l'installation
- 📊 **Monitoring intégré** : Health checks et logs

Cette structure permet à SSDV2 de s'adapter parfaitement à Redriva ! 🎉
