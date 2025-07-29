# Redriva

Outil de synchronisation Python pour archiver vos torrents Real-Debrid dans une base de données SQLite locale.

## 📋 Description

Redriva récupère automatiquement tous vos torrents et leurs détails depuis l'API Real-Debrid pour les stocker localement. Cela permet d'avoir un historique complet, des statistiques et de faire des recherches sans solliciter l'API en permanence.

## 🚀 Installation

```bash
git clone https://github.com/votre-username/Redriva.git
cd Redriva

# Installation des dépendances
pip install -r requirements.txt
# ou
pip install aiohttp

# Configuration automatique (recommandé)
./setup.sh

# OU configuration manuelle :
mkdir -p config data
```

## ⚙️ Configuration

### Token Real-Debrid

**⚠️ Important :** Votre token Real-Debrid est sensible et ne doit jamais être partagé !

#### Comment obtenir votre token Real-Debrid

1. Connectez-vous sur [Real-Debrid](https://real-debrid.com)
2. Allez dans **Mon compte** → **API**
3. Copiez votre token d'accès

#### Configuration du token

**Option 1 : Variable d'environnement (recommandée)**
```bash
export RD_TOKEN="votre_token_real_debrid"
```

**Option 2 : Fichier de configuration**
```bash
# Copiez le fichier d'exemple
cp config/rd_token.conf.example config/rd_token.conf

# Éditez le fichier avec votre token
nano config/rd_token.conf
```

**Option 3 : Fichier .env**
```bash
# Copiez le fichier d'exemple
cp .env.example .env

# Éditez le fichier avec vos paramètres
nano .env
```

### Variables d'environnement optionnelles

```bash
export RD_MAX_CONCURRENT=50    # Requêtes simultanées (défaut: 50)
export RD_BATCH_SIZE=250       # Taille des batches (défaut: 250)
export RD_QUOTA_WAIT=60        # Attente quota global (défaut: 60s)
export RD_TORRENT_WAIT=10      # Attente quota torrent (défaut: 10s)
```

## 📖 Utilisation

### Synchronisation complète
```bash
python src/main.py --sync-all
```
Récupère tous les torrents et leurs détails depuis Real-Debrid (version classique).

### Synchronisation des torrents uniquement 📋
```bash
python src/main.py --torrents-only
```
Récupère uniquement la liste des torrents de base (très rapide, sans détails).

### Synchronisation rapide 🚀
```bash
python src/main.py --sync-fast
```
Version optimisée avec contrôle dynamique de la concurrence et reprise automatique.

### Synchronisation intelligente 🧠
```bash
python src/main.py --sync-smart
```
Ne synchronise que les torrents modifiés ou sans détails (très rapide pour les mises à jour).

**Options avancées :**
```bash
# Afficher ce qui serait synchronisé sans le faire
python src/main.py --sync-smart --dry-run

# Mode détaillé avec plus d'informations
python src/main.py --sync-smart --verbose

# Seulement les changements de statut (plus rapide)
python src/main.py --sync-smart --status-changes-only

# Inclure les téléchargements actifs (par défaut exclus)
python src/main.py --sync-smart --include-active-downloads

# Ignorer les tentatives de retry d'erreurs
python src/main.py --sync-smart --skip-error-retry
```

**Que fait sync-smart exactement :**
- ✅ **Détecte les nouveaux torrents** ajoutés à Real-Debrid
- ✅ **Identifie les changements de statut** (downloading → downloaded, etc.)
- ✅ **Met à jour les téléchargements actifs** (en cours, en attente)
- ✅ **Récupère les détails manquants** des torrents sans informations complètes
- ✅ **Retry intelligent des erreurs** pour les torrents qui étaient en erreur
- ✅ **Ordre de priorité** : nouveaux → changements → actifs → retry → manquants

### Reprendre une synchronisation ⏮️
```bash
python src/main.py --resume
```
Reprend une synchronisation interrompue là où elle s'était arrêtée.

### Synchronisation des détails uniquement
```bash
python src/main.py --details-only
```
Met à jour uniquement les détails des torrents déjà présents en base.

### Filtrage par status
```bash
python src/main.py --details-only --status downloaded
python src/main.py --details-only --status error
```

### Statistiques
```bash
python src/main.py --stats
```
Affiche un résumé des données en base.

### Vider la base de données
```bash
python src/main.py --clear
```
Supprime toutes les données de la base (demande confirmation).

## 🗄️ Structure de la base de données

### Table `torrents`
- `id` : Identifiant unique du torrent
- `filename` : Nom du fichier
- `status` : Statut (downloaded, error, etc.)
- `bytes` : Taille en octets
- `added_on` : Date d'ajout

### Table `torrent_details`  
- `id` : Identifiant unique (clé étrangère)
- `name` : Nom complet
- `status` : Statut détaillé
- `size` : Taille en octets
- `files_count` : Nombre de fichiers
- `progress` : Progression (0-100)
- `links` : Liens de téléchargement (CSV)
- `hash` : Hash du torrent
- `host` : Hébergeur
- `error` : Message d'erreur éventuel
- ... et plus

## 🔧 Fonctionnalités

- ✅ **Sync asynchrone** : Récupération rapide avec contrôle de concurrence
- ✅ **Gestion des quotas** : Respect automatique des limites API
- ✅ **Retry intelligent** : Backoff exponentiel en cas d'erreur
- ✅ **Interruption propre** : Support CTRL+C sans corruption
- ✅ **Configuration flexible** : Variables d'environnement
- ✅ **Logging détaillé** : Suivi en temps réel des opérations
- ✅ **Sync rapide** : Contrôle dynamique de concurrence (nouveau)
- ✅ **Sync intelligente** : Seulement les changements (nouveau)
- ✅ **Reprise automatique** : Continue après interruption (nouveau)

## ⚡ Performances

### Comparaison des vitesses (testé sur 3883 torrents)

| Mode | Temps | Vitesse | Usage recommandé |
|------|-------|---------|------------------|
| `--sync-all` (classique) | 4-6 heures | 0.2-0.3/s | Version stable de référence |
| `--sync-fast` 🚀 | **7.3 minutes** | **8.9/s** | Synchronisation complète rapide |
| `--sync-smart` 🧠 | 1-3 minutes | 15-30/s | Mises à jour quotidiennes |
| `--torrents-only` 📋 | 30-60 secondes | 50-100/s | Vue d'ensemble ultra-rapide |
| `--resume` ⏮️ | Variable | 8.9/s | Reprise après interruption |

**Workflow recommandé avec les options avancées**

```bash
# 1. Premier sync complet (une fois) - 7 minutes
python src/main.py --sync-fast

# 2. Vérifier ce qui changerait avant de synchroniser
python src/main.py --sync-smart --dry-run --verbose

# 3. Mises à jour quotidiennes - 1-2 minutes  
python src/main.py --sync-smart

# 4. Sync ultra-rapide (seulement les changements de statut)
python src/main.py --sync-smart --status-changes-only

# 5. Vue d'ensemble rapide - 30 secondes
python src/main.py --torrents-only

# 6. Si interruption pendant un gros sync
python src/main.py --resume
```

**Exemples d'usage spécialisés :**

```bash
# Sync avec informations détaillées
python src/main.py --sync-smart --verbose

# Sync sans retry des erreurs (plus rapide)  
python src/main.py --sync-smart --skip-error-retry

# Voir ce qui serait mis à jour sans le faire
python src/main.py --sync-smart --dry-run

# Sync incluant les téléchargements actifs
python src/main.py --sync-smart --include-active-downloads
```

## 📊 Exemples de requêtes SQL

### Torrents par statut
```sql
SELECT status, COUNT(*) as count 
FROM torrents 
GROUP BY status;
```

### Torrents les plus volumineux
```sql
SELECT filename, bytes/1024/1024/1024 as size_gb 
FROM torrents 
ORDER BY bytes DESC 
LIMIT 10;
```

### Progression moyenne
```sql
SELECT AVG(progress) as avg_progress 
FROM torrent_details 
WHERE status = 'downloading';
```

## 🐛 Dépannage

### Erreur "Token invalide"
Vérifiez que votre token Real-Debrid est valide et configuré correctement.

### Quota API dépassé
L'outil gère automatiquement les quotas avec des pauses. Ajustez `RD_QUOTA_WAIT` si nécessaire.

### Interruption réseau
Le système de retry automatique gère les coupures temporaires.

## 📁 Structure du projet

```
Redriva/
├── README.md
├── config/
│   └── rd_token.conf          # Token Real-Debrid
├── data/
│   └── redriva.db            # Base SQLite (auto-générée)
└── src/
    └── main.py               # Script principal
```

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou proposer une pull request.

## 📝 Licence

MIT License - Voir le fichier LICENSE pour plus de détails.