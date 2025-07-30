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
pip install aiohttp flask

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

**Configuration unique dans config/.env :**
```bash
# 1. Copiez le fichier d'exemple
cp config/.env.example config/.env

# 2. Éditez le fichier avec votre token
nano config/.env

# 3. Remplacez 'votre_token_ici' par votre vrai token Real-Debrid
RD_TOKEN=votre_token_real_debrid_ici
```

### Variables d'environnement optionnelles

Vous pouvez aussi définir ces variables dans `config/.env` :

```bash
RD_MAX_CONCURRENT=50    # Requêtes simultanées (défaut: 50)
RD_BATCH_SIZE=250       # Taille des batches (défaut: 250)
RD_QUOTA_WAIT=60        # Attente quota global (défaut: 60s)
RD_TORRENT_WAIT=10      # Attente quota torrent (défaut: 10s)
RD_PAGE_WAIT=1.0        # Attente entre pages (défaut: 1.0s)
```

## 🎮 Menu Interactif

**Lancez Redriva sans arguments pour accéder au menu convivial :**

```bash
python src/main.py
```

**Fonctionnalités du menu :**
- 🎯 **Interface guidée** : Choix numérotés avec descriptions claires
- ⚡ **Actions rapides** : Accès direct aux fonctions principales  
- 💡 **Guide intégré** : Recommandations selon votre usage
- 🔄 **Navigation fluide** : Retour automatique au menu après chaque action
- 🏃 **Mode hybride** : Basculement vers ligne de commande si besoin

**Utilisation recommandée :**
- 🥇 **Première utilisation** : Menu → Choix 5 (Sync rapide complet)
- � **Usage quotidien** : Menu → Choix 2 + 4 (Stats + Sync intelligent)  
- 🔧 **Maintenance** : Menu → Choix 1 + 3 (Stats complètes + Diagnostic)

## 📖 Usage en ligne de commande

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
- ✅ **Analyse pré-synchronisation** : Détecte précisément les changements avant de commencer
- ✅ **Nouveaux torrents** : Identifie les torrents ajoutés sans détails
- ✅ **Téléchargements actifs** : Met à jour les torrents en cours (downloading, queued)
- ✅ **Retry intelligent** : Retente automatiquement les torrents en erreur
- ✅ **Torrents anciens** : Rafraîchit les données de plus de 7 jours
- ✅ **Priorité optimisée** : Traite d'abord les plus importants
- ✅ **Statistiques temps réel** : Affiche vitesse, ETA et progression
- ✅ **Résumé post-sync** : Analyse complète des résultats avec recommandations

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

### Diagnostic des erreurs 🔍
```bash
python src/main.py --diagnose-errors
```
Diagnostique détaillé des torrents en erreur avec :
- **Informations complètes** : ID, nom, statut, message d'erreur, progression
- **Analyse automatique** : Type d'erreur (timeout, 404, quota, etc.)
- **Suggestions ciblées** : Actions recommandées selon le type d'erreur
- **Résumé par type** : Répartition des erreurs par catégorie
- **Actions correctives** : Commandes exactes pour résoudre les problèmes

**Exemple de sortie :**
```
🔍 DIAGNOSTIC DES ERREURS (2 torrents)

❌ ERREUR #1
   🆔 ID             : 6EFUCLXXXPINY
   📁 Nom            : Mr.XXX.20XX.FRENCH.BDRip.x264-UTT.mkv
   📊 Statut         : error
   ⚠️  Message d'erreur: Timeout after 30s
   🔬 Type d'erreur  : ⏱️ Timeout réseau (temporaire)
   💡 Suggestion     : 🔄 Retry automatique recommandé

📊 RÉSUMÉ DES TYPES D'ERREURS
   • ⏱️ Timeout réseau (temporaire) : 1
   • 🔍 Torrent introuvable (supprimé de RD) : 1

💡 ACTIONS RECOMMANDÉES :
   🔄 Retry automatique    : python src/main.py --sync-smart
   🎯 Retry forcé          : python src/main.py --details-only --status error
```

### Statistiques détaillées 📊
```bash
python src/main.py --stats
```
Affiche des statistiques complètes et détaillées de votre collection :
- **Vue d'ensemble** : total, couverture, détails manquants
- **Volumes de données** : taille totale, moyenne, min/max
- **Activité récente** : torrents des dernières 24h et 7 jours
- **État des téléchargements** : progression, actifs, erreurs
- **Répartition par statut** : avec pourcentages et emojis
- **Top hébergeurs** : les plus utilisés
- **Plus gros torrents** : top 5 avec tailles
- **Recommandations** : actions suggérées automatiquement

**Version compacte :**
```bash
python src/main.py --stats --compact
```
Affichage sur une ligne : `📊 4,233 torrents | 4,232 détails (100.0%) | ⬇️ 0 en cours | ❌ 2 erreurs`

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

- ✅ **Synchronisation asynchrone** : Récupération rapide avec contrôle de concurrence
- ✅ **Contrôle dynamique** : Ajustement automatique de la concurrence selon les performances
- ✅ **Gestion intelligente des quotas** : Respect automatique des limites API avec pauses adaptatives
- ✅ **Système de retry avancé** : Backoff exponentiel en cas d'erreur avec récupération automatique
- ✅ **Interruption propre** : Support CTRL+C sans corruption de données
- ✅ **Configuration flexible** : Variables d'environnement et fichiers .env
- ✅ **Logging détaillé** : Suivi en temps réel avec statistiques de performance
- ✅ **Reprise automatique** : Continue les synchronisations interrompues
- ✅ **Synchronisation intelligente** : Détecte et synchronise uniquement les changements
- ✅ **Statistiques enrichies** : Analyse complète avec recommandations automatiques
- ✅ **Sauvegarde progressive** : Protection contre les interruptions lors des gros sync
- ✅ **Pool de connexions optimisé** : Performance maximale avec gestion des timeouts
- ✅ **Interface web complète** : Dashboard, navigation, logs temps réel, actions de sync

## 🌐 Interface Web

Redriva dispose d'une **interface web moderne et complètement fonctionnelle** pour visualiser vos données et lancer des actions facilement.

### 🚀 Lancement de l'interface web

```bash
# Démarrer le serveur web
python src/web.py

# L'interface sera accessible sur : http://127.0.0.1:5000
# Arrêt propre avec : Ctrl+C
```

### ✨ Fonctionnalités complètes

#### 📊 **Dashboard interactif**
- **Cartes statistiques cliquables** : Navigation directe vers les sections (erreurs, téléchargements, etc.)
- **Actions de synchronisation** : 4 modes disponibles avec confirmations et logs temps réel
- **Console d'activité** : Logs en temps réel avec auto-scroll et contrôles
- **Design moderne** : Interface responsive avec animations et notifications

#### 📋 **Liste des torrents**
- **Pagination intelligente** : Navigation fluide (50 torrents par page)
- **Filtres dynamiques** : Par statut avec compteurs automatiques
- **Recherche textuelle** : Dans noms de fichiers et descriptions
- **Badges colorés** : Identification rapide des statuts (✅ Downloaded, ⬇️ Downloading, ❌ Error, etc.)

#### 🔍 **Détails torrent**
- **Informations complètes** : ID, Hash, Taille, Statut, Progression
- **Liens de téléchargement** : Liste de tous les fichiers disponibles
- **Historique des erreurs** : Détails complets des problèmes rencontrés
- **Actions avancées** : Retry, copie d'infos, téléchargement groupé

### � **Documentation Web Complète**

#### 🔹 **Guide Utilisateur**
📖 **[WEBAPP_GUIDE.md](WEBAPP_GUIDE.md)** - Guide complet de l'interface web
```
- 🎯 Introduction et démarrage rapide
- 📊 Dashboard principal et cartes interactives  
- 🔄 Actions de synchronisation avec logs temps réel
- 🔍 Navigation et filtres avancés
- 📱 Interface utilisateur et design responsive
- 🛠️ Troubleshooting et configuration
- 📈 Métriques et analytics
```

#### 🔹 **Documentation Technique**
🏗️ **[WEBAPP_TECHNICAL.md](WEBAPP_TECHNICAL.md)** - Architecture et développement
```
- 🏛️ Architecture générale (MVC, Stack technologique)
- 📁 Structure des fichiers et responsabilités
- 🐍 Backend Flask avec routes et contrôleurs
- 🎨 Frontend et templates Jinja2
- 💾 Base de données et requêtes optimisées
- 🔌 API REST et endpoints JSON
- 📊 Système de logs et monitoring
- ⚡ Performance et optimisation
- 🧪 Tests et debugging
- 🚀 Déploiement en production
```

### 🌟 **Pages disponibles**

| Route | Description | Fonctionnalités |
|-------|-------------|-----------------|
| `/` | Dashboard principal | **Cartes cliquables**, statistiques, logs temps réel |
| `/torrents` | Liste complète paginée | Filtres, recherche, pagination |
| `/torrents?status=error` | Torrents en erreur | Filtrage automatique, actions de retry |
| `/torrent/<id>` | Détail spécifique | Infos complètes, liens, actions |
| `/sync/<mode>` | Actions de sync | smart, fast, torrents, errors |

### 🎯 **Exemple d'utilisation**

```bash
# 1. Lancer l'interface
python src/web.py

# 2. Ouvrir http://127.0.0.1:5000 dans votre navigateur

# 3. Utiliser l'interface :
# - Cliquer sur les cartes statistiques pour naviguer
# - Lancer une synchronisation et voir les logs en temps réel
# - Filtrer vos torrents par statut (erreurs, téléchargements)
# - Consulter les détails d'un torrent spécifique
```

### 📈 **Exemple de collection réelle**

L'interface web de Redriva gère efficacement des collections importantes :

```
📊 Collection de test en production :
   🗂️  Torrents totaux     : 4,245
   📋 Avec détails         : 4,232 (99.7% de couverture)
   💾 Taille totale        : 15.3 TB
   🆕 Ajouts récents (24h) : 42 torrents
   ❌ Erreurs              : 2 seulement (0.05%)
   ✅ Téléchargements OK   : 4,230
```

> 💡 **Performance** : L'interface reste fluide même avec des milliers de torrents grâce à la pagination intelligente et aux requêtes SQL optimisées.

### 🛑 **Arrêt et gestion**

```bash
# Arrêt normal (recommandé)
Ctrl+C

# Arrêt forcé si bloqué
./stop_web.sh

# Vérification du statut
lsof -i:5000
```

## ⚡ Performances

### Comparaison des vitesses (testé sur 4,233 torrents)

| Mode | Temps | Vitesse | Usage recommandé |
|------|-------|---------|------------------|
| `--sync-all` (classique) | 4-6 heures | 0.2-0.3/s | Première synchronisation complète |
| `--sync-fast` 🚀 | **7-10 minutes** | **8-12/s** | Synchronisation complète optimisée |
| `--sync-smart` 🧠 | **30s-2 minutes** | **15-50/s** | Mises à jour quotidiennes (recommandé) |
| `--torrents-only` 📋 | **10-30 secondes** | **50-200/s** | Vue d'ensemble ultra-rapide |
| `--resume` ⏮️ | Variable | 8-12/s | Reprise après interruption |
| `--stats` 📊 | **<1 seconde** | Instantané | Monitoring et analyse |
| `--stats --compact` | **<1 seconde** | Instantané | Check rapide |

**Workflow recommandé avec analyse intelligente**

```bash
# 1. Premier sync complet (une fois) - 7-10 minutes
python src/main.py --sync-fast

# 2. Check rapide quotidien - <1 seconde  
python src/main.py --stats --compact

# 3. Mises à jour intelligentes - 30s-2 minutes  
python src/main.py --sync-smart

# 4. Interface web pour monitoring - Instantané
python src/web.py
# Puis http://127.0.0.1:5000

# 5. Analyse détaillée si nécessaire
python src/main.py --stats

# 6. Vue d'ensemble rapide - 10-30 seconds
python src/main.py --torrents-only

# 6. Si interruption pendant un gros sync
python src/main.py --resume
```

**Exemples d'usage spécialisés :**

```bash
# Monitoring rapide (idéal pour scripts/cron)
python src/main.py --stats --compact

# Analyse complète avec recommandations
python src/main.py --stats

# Diagnostic détaillé des problèmes
python src/main.py --diagnose-errors

# Sync intelligent avec détection des changements
python src/main.py --sync-smart

# Retry des torrents en erreur uniquement
python src/main.py --details-only --status error

# Vérification d'un statut spécifique  
python src/main.py --details-only --status downloading
```

## 📊 Analyse et Monitoring

### Statistiques complètes
```bash
python src/main.py --stats
```

**Exemple de sortie :**
```
============================================================
📊 STATISTIQUES COMPLÈTES REDRIVA
============================================================

🗂️  VUE D'ENSEMBLE
   📁 Total torrents     : 4,233
   📋 Détails disponibles: 4,232
   📊 Couverture         : 100.0%
   ❌ Détails manquants  : 1

💾 VOLUMES DE DONNÉES
   📦 Volume total       : 15.2 TB
   📊 Taille moyenne     : 3.7 GB
   🔻 Plus petit         : 112.6 MB
   🔺 Plus gros          : 45.5 GB

⏰ ACTIVITÉ RÉCENTE
   🆕 Dernières 24h      : 35 torrents
   📅 Derniers 7 jours   : 1,156 torrents

🔄 ÉTAT DES TÉLÉCHARGEMENTS
   ✅ Progression moyenne: 100.0%
   ⬇️  Téléchargements    : 0
   ❌ Erreurs            : 2

📈 RÉPARTITION PAR STATUT
   ✅ downloaded      : 4,229 (99.9%)
   ❌ error           : 2 (0.0%)
   ⬇️ downloading     : 2 (0.0%)

🌐 TOP HÉBERGEURS
   🔗 real-debrid.com : 4,232 (100.0%)

🏆 TOP 5 PLUS GROS TORRENTS
   1. ✅ 45.5 GB - Foundation.S01.MULTi.1080p.ATVP.WEB-DL...
   2. ✅ 44.1 GB - Foundation.S02.MULTI.1080p.WEB.H264...

💡 RECOMMANDATIONS
   🔧 Exécuter: python src/main.py --sync-smart
      (pour récupérer 1 détails manquants)
   🔄 Exécuter: python src/main.py --details-only --status error
      (pour retry 2 torrents en erreur)
============================================================
```

### Monitoring rapide
```bash
python src/main.py --stats --compact
# Sortie : 📊 4,233 torrents | 4,232 détails (100.0%) | ⬇️ 0 en cours | ❌ 2 erreurs
```

### Informations fournies
- **Couverture complète** des données avec pourcentages
- **Volumes détaillés** : espace utilisé, moyennes, extrêmes
- **Activité temporelle** : ajouts récents (24h, 7j)
- **État en temps réel** : téléchargements actifs, erreurs
- **Analyse des hébergeurs** : répartition par service
- **Top torrents** : les plus volumineux avec statuts
- **Recommandations automatiques** : actions suggérées selon l'état

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
├── README.md                    # Documentation complète
├── LICENSE                      # Licence MIT
├── SECURITY.md                  # Politique de sécurité
├── CONTRIBUTING.md              # Guide de contribution
├── requirements.txt             # Dépendances Python
├── setup.sh                     # Script de configuration automatique
├── .env.example                 # Modèle de configuration
├── .gitignore                   # Protection fichiers sensibles
├── config/
│   ├── rd_token.conf           # Token Real-Debrid (ignoré par Git)
│   └── rd_token.conf.example   # Modèle de token
├── data/
│   ├── redriva.db              # Base SQLite (auto-générée)
│   └── sync_progress.json      # Progression des sync (temporaire)
└── src/
    ├── main.py                 # Script principal avec toutes les fonctionnalités
    └── main.py.backup          # Sauvegarde automatique
```

## 📁 Structure du projet

```
Redriva/
├── README.md                    # Documentation complète
├── LICENSE                      # Licence MIT
├── SECURITY.md                  # Politique de sécurité
├── CONTRIBUTING.md              # Guide de contribution
├── requirements.txt             # Dépendances Python
├── setup.sh                     # Script de configuration automatique
├── .env.example                 # Modèle de configuration
├── .gitignore                   # Protection fichiers sensibles
├── config/
│   ├── rd_token.conf           # Token Real-Debrid (ignoré par Git)
│   └── rd_token.conf.example   # Modèle de token
├── data/
│   ├── redriva.db              # Base SQLite (auto-générée)
│   └── sync_progress.json      # Progression des sync (temporaire)
└── src/
    ├── main.py                 # Script principal réorganisé par sections
    └── main.py.backup          # Sauvegarde automatique
```

### Architecture du script principal

Le fichier `src/main.py` est organisé en **9 sections claires** pour une maintenance optimale :

```python
# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 1: IMPORTS ET CONFIGURATION         ║
# ╚════════════════════════════════════════════════════════╝
# - Imports et variables d'environnement
# - Configuration logging et signaux
# - Constantes et paramètres globaux

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 2: UTILITAIRES ET HELPERS           ║
# ╚════════════════════════════════════════════════════════╝
# - format_size(), get_status_emoji()
# - Fonctions de conversion et formatage
# - Helpers de sécurité (safe_int, safe_float)

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 3: BASE DE DONNÉES                  ║
# ╚════════════════════════════════════════════════════════╝
# - create_tables(), get_db_stats()
# - Gestion SQLite et structure données
# - Fonctions de maintenance base

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 4: API REAL-DEBRID                  ║
# ╚════════════════════════════════════════════════════════╝
# - api_request(), fetch_all_torrents()
# - Communication avec l'API Real-Debrid
# - Gestion tokens et authentification

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 5: SYNCHRONISATION                  ║
# ╚════════════════════════════════════════════════════════╝
# - sync_smart(), sync_all_v2(), sync_resume()
# - Moteurs de synchronisation optimisés
# - Contrôle dynamique et reprise auto

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 6: STATISTIQUES ET ANALYTICS        ║
# ╚════════════════════════════════════════════════════════╝
# - show_stats(), show_stats_compact()
# - Analytics avancées et recommandations
# - Métriques de performance

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 7: DIAGNOSTIC ET MAINTENANCE        ║
# ╚════════════════════════════════════════════════════════╝
# - diagnose_errors(), analyze_error_type()
# - Diagnostic automatique des problèmes
# - Suggestions de correction

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 8: INTERFACE UTILISATEUR (MENU)     ║
# ╚════════════════════════════════════════════════════════╝
# - show_interactive_menu(), show_quick_guide()
# - Menu interactif avec guide intégré
# - Navigation conviviale

# ╔════════════════════════════════════════════════════════╗
# ║            SECTION 9: POINT D'ENTRÉE PRINCIPAL         ║
# ╚════════════════════════════════════════════════════════╝
# - main(), gestion arguments CLI
# - Logique de démarrage et orchestration
# - Support menu interactif + arguments
```

**Avantages de cette organisation :**
- ✅ **Navigation facile** : Sections clairement délimitées avec séparateurs visuels
- ✅ **Maintenance simplifiée** : Code organisé par responsabilité  
- ✅ **Documentation inline** : Chaque fonction documentée avec exemples
- ✅ **Claude/Copilot friendly** : Structure claire pour IA de maintenance
- ✅ **Évolutivité** : Ajout de fonctionnalités sans impact sur l'existant

### Fonctionnalités du script principal

- **Synchronisation** : `--sync-all`, `--sync-fast`, `--sync-smart`
- **Monitoring** : `--stats`, `--stats --compact`
- **Diagnostic** : `--diagnose-errors` (nouveau)
- **Maintenance** : `--resume`, `--details-only`, `--clear`
- **Vues spécialisées** : `--torrents-only`
- **Configuration** : Support `.env`, variables d'environnement
- **Sécurité** : Protection des tokens, gestion des erreurs
- **Performance** : Contrôle dynamique, pools de connexions optimisés

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou proposer une pull request.

## 📝 Licence

MIT License - Voir le fichier LICENSE pour plus de détails.