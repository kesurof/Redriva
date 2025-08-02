# 🔗 PLAN D'INTÉGRATION SYMLINK MANAGER DANS REDRIVA

## 🎯 OBJECTIF
Intégrer le script `advanced_symlink_detector` dans Redriva avec une interface web complète, sans modifier le code existant.

## 📁 ARCHITECTURE CHOISIE
**Approche simplifiée** : 3 fichiers principaux pour faciliter la génération IA
- `src/symlink_tool.py` - Backend complet (classe + API)
- `src/templates/symlink_tool.html` - Interface web complète
- `src/static/js/symlink_tool.js` - Logique frontend

---

## 🚀 ROADMAP D'IMPLÉMENTATION

### ✅ PHASE 1 : PRÉPARATION DE L'ENVIRONNEMENT

#### 1.1 Modifications Docker
- [x] **Mise à jour `docker-compose.yml`**
  - Ajouter le volume `./medias:/app/medias:rw`
  - Documenter la configuration du lien symbolique

#### 1.2 Structure des fichiers
- [x] **Créer les répertoires manquants**
  - Vérifier `src/static/js/` existe
  - Créer `./medias/` si nécessaire

---

### ✅ PHASE 2 : BACKEND (symlink_tool.py)

#### 2.1 Modèles de base de données
- [x] **Créer les modèles SQLAlchemy**
  ```python
  class SymlinkConfig(db.Model):
      - id (Primary Key)
      - media_path (String, default="/app/medias")
      - max_workers (Integer, default=6)
      - sonarr_enabled (Boolean)
      - sonarr_host, sonarr_port, sonarr_api_key
      - radarr_enabled (Boolean)
      - radarr_host, radarr_port, radarr_api_key
      - created_at, updated_at
  
  class SymlinkScan(db.Model):
      - id (Primary Key)
      - scan_date (DateTime)
      - mode (String: 'dry-run' ou 'real')
      - selected_paths (JSON)
      - verification_depth (String: 'basic' ou 'full')
      - total_analyzed (Integer)
      - phase1_ok, phase1_broken, phase1_inaccessible, phase1_small, phase1_io_error
      - phase2_analyzed, phase2_corrupted
      - files_deleted (Integer)
      - duration (Float)
      - status (String: 'running', 'completed', 'cancelled', 'error')
      - results_json (Text) - stockage temporaire des résultats
  ```

#### 2.2 Adaptation de la classe AdvancedSymlinkChecker
- [x] **Copier et adapter la classe depuis `advanced_symlink_detector`**
  - Remplacer tous les `input()` par des paramètres de méthodes
  - Adapter les `print()` pour retourner des données JSON/structures
  - Implémenter un système de callback pour le progress
  - Intégrer la configuration depuis la base de données
  - Gérer l'interruption via un flag plutôt que KeyboardInterrupt

#### 2.3 Système de tâches asynchrones
- [x] **Créer le gestionnaire de tâches**
  ```python
  class SymlinkTaskManager:
      - Gestion des tâches en arrière-plan avec threading
      - États : pending, running, completed, cancelled, error
      - Système de progress callbacks
      - Stockage temporaire des résultats
      - Rotation automatique (3 derniers scans)
  ```

#### 2.4 Endpoints API
- [x] **GET `/api/symlink/config`** - Récupérer la configuration actuelle
- [x] **POST `/api/symlink/config`** - Sauvegarder la configuration
- [x] **GET `/api/symlink/directories`** - Lister les répertoires disponibles avec compteurs
- [x] **POST `/api/symlink/scan/start`** - Démarrer un nouveau scan
- [x] **GET `/api/symlink/scan/status/<scan_id>`** - Statut du scan en cours
- [x] **POST `/api/symlink/scan/cancel/<scan_id>`** - Annuler un scan en cours
- [x] **GET `/api/symlink/scans/history`** - Historique des 3 derniers scans
- [x] **POST `/api/symlink/test/services`** - Tester les connexions Sonarr/Radarr
- [x] **POST `/api/symlink/services/detect`** - Auto-détection des services Docker

---

### ✅ PHASE 3 : FRONTEND (symlink_tool.html)

#### 3.1 Structure HTML de base
- [x] **Hériter de `base.html`**
- [x] **Créer la structure à onglets**
  - Dashboard (historique + vue d'ensemble)
  - Scanner (interface de scan)
  - Settings (configuration)

#### 3.2 Onglet Dashboard
- [x] **Vue d'ensemble**
  - Statut du service (prêt/en cours)
  - Bouton "Nouveau scan" prominent
- [x] **Tableau historique des 3 derniers scans**
  - Date, mode, durée, résultats
  - Bouton pour voir les détails
  - Bouton pour relancer avec les mêmes paramètres

#### 3.3 Onglet Scanner
- [x] **Formulaire de configuration du scan**
  - Sélection des répertoires (avec compteurs de symlinks)
  - Mode d'exécution (dry-run/real)
  - Profondeur de vérification (basic/full)
- [x] **Interface de progression temps réel**
  - Barre de progression globale
  - Détail des phases (Phase 1, Phase 2)
  - Statistiques live
  - Bouton d'annulation
- [x] **Affichage des résultats**
  - Tableau des problèmes détectés
  - Filtres par type de problème
  - Actions possibles (voir détails, ignorer)
  - Confirmation avant suppression en mode réel

#### 3.4 Onglet Settings
- [x] **Configuration générale**
  - Chemin des médias (avec validation)
  - Nombre de workers parallèles
- [x] **Configuration Sonarr**
  - Activation on/off
  - Host, port, API key
  - Bouton de test de connexion
- [x] **Configuration Radarr**
  - Activation on/off
  - Host, port, API key
  - Bouton de test de connexion
- [x] **Bouton auto-détection des services Docker**

---

### ✅ PHASE 4 : JAVASCRIPT (symlink_tool.js)

#### 4.1 Gestion des onglets
- [x] **Navigation entre onglets avec état persistant**
- [x] **Chargement dynamique du contenu**

#### 4.2 Communication API
- [x] **Fonctions d'appels API pour tous les endpoints**
- [x] **Gestion des erreurs et timeouts**
- [x] **Système de polling pour le suivi des scans**

#### 4.3 Interface Scanner
- [x] **Sélection interactive des répertoires**
  - Chargement dynamique de l'arborescence
  - Compteurs de liens symboliques
  - Sélection multiple avec "tout sélectionner"
- [x] **Gestion du scan en temps réel**
  - Démarrage du scan avec validation
  - Mise à jour de la progression via polling
  - Gestion de l'annulation
- [x] **Interface de confirmation**
  - Modal de confirmation avant suppression
  - Option "voir plus de détails"

#### 4.4 Interface Settings
- [x] **Validation des formulaires**
- [x] **Tests de connexion asynchrones**
- [x] **Auto-détection des services Docker**
- [x] **Sauvegarde automatique des modifications**

---

### ✅ PHASE 5 : INTÉGRATION DANS REDRIVA

#### 5.1 Modification du menu principal
- [x] **Ajouter "Symlink" dans `base.html`**
  ```html
  <a href="/symlink">🔗 Symlink</a>
  ```

#### 5.2 Route Flask principale
- [x] **Ajouter dans `web.py`**
  ```python
  @app.route('/symlink')
  def symlink_manager():
      return render_template('symlink_tool.html')
  ```

#### 5.3 Import des dépendances
- [x] **Ajouter les imports nécessaires dans `web.py`**
- [x] **Initialiser les tables de base de données**

---

### ✅ PHASE 3 : FRONTEND (symlink_tool.html)

#### 3.1 Structure HTML de base
- [ ] **Hériter de `base.html`**
- [ ] **Créer la structure à onglets**
  - Dashboard (historique + vue d'ensemble)
  - Scanner (interface de scan)
  - Settings (configuration)

#### 3.2 Onglet Dashboard
- [ ] **Vue d'ensemble**
  - Statut du service (prêt/en cours)
  - Bouton "Nouveau scan" prominent
- [ ] **Tableau historique des 3 derniers scans**
  - Date, mode, durée, résultats
  - Bouton pour voir les détails
  - Bouton pour relancer avec les mêmes paramètres

#### 3.3 Onglet Scanner
- [ ] **Formulaire de configuration du scan**
  - Sélection des répertoires (avec compteurs de symlinks)
  - Mode d'exécution (dry-run/real)
  - Profondeur de vérification (basic/full)
- [ ] **Interface de progression temps réel**
  - Barre de progression globale
  - Détail des phases (Phase 1, Phase 2)
  - Statistiques live
  - Bouton d'annulation
- [ ] **Affichage des résultats**
  - Tableau des problèmes détectés
  - Filtres par type de problème
  - Actions possibles (voir détails, ignorer)
  - Confirmation avant suppression en mode réel

#### 3.4 Onglet Settings
- [ ] **Configuration générale**
  - Chemin des médias (avec validation)
  - Nombre de workers parallèles
- [ ] **Configuration Sonarr**
  - Activation on/off
  - Host, port, API key
  - Bouton de test de connexion
- [ ] **Configuration Radarr**
  - Activation on/off
  - Host, port, API key
  - Bouton de test de connexion
- [ ] **Bouton auto-détection des services Docker**

---

### ✅ PHASE 4 : JAVASCRIPT (symlink_tool.js)

#### 4.1 Gestion des onglets
- [ ] **Navigation entre onglets avec état persistant**
- [ ] **Chargement dynamique du contenu**

#### 4.2 Communication API
- [ ] **Fonctions d'appels API pour tous les endpoints**
- [ ] **Gestion des erreurs et timeouts**
- [ ] **Système de polling pour le suivi des scans**

#### 4.3 Interface Scanner
- [ ] **Sélection interactive des répertoires**
  - Chargement dynamique de l'arborescence
  - Compteurs de liens symboliques
  - Sélection multiple avec "tout sélectionner"
- [ ] **Gestion du scan en temps réel**
  - Démarrage du scan avec validation
  - Mise à jour de la progression via polling
  - Affichage des statistiques live
  - Gestion de l'annulation
- [ ] **Interface de confirmation**
  - Modal de confirmation avant suppression
  - Détail des fichiers à supprimer
  - Option "voir plus de détails"

#### 4.4 Interface Settings
- [ ] **Validation des formulaires**
- [ ] **Tests de connexion asynchrones**
- [ ] **Auto-détection des services Docker**
- [ ] **Sauvegarde automatique des modifications**

---

### ✅ PHASE 5 : INTÉGRATION DANS REDRIVA

#### 5.1 Modification du menu principal
- [ ] **Ajouter "Symlink" dans `base.html`**
  ```html
  <a href="/symlink">🔗 Symlink</a>
  ```

#### 5.2 Route Flask principale
- [ ] **Ajouter dans `web.py`**
  ```python
  @app.route('/symlink')
  def symlink_manager():
      return render_template('symlink_tool.html')
  ```

#### 5.3 Import des dépendances
- [ ] **Ajouter les imports nécessaires dans `web.py`**
- [ ] **Initialiser les tables de base de données**

---

### ✅ PHASE 6 : TESTS ET OPTIMISATIONS

#### 6.1 Tests fonctionnels
- [ ] **Test de l'interface utilisateur**
  - Navigation entre onglets
  - Formulaires de configuration
  - Validation des champs
- [ ] **Test des API endpoints**
  - Configuration CRUD
  - Démarrage/arrêt des scans
  - Récupération des statuts
- [ ] **Test de l'intégration Docker**
  - Montage des volumes
  - Accès aux fichiers
  - Détection des services

#### 6.2 Tests de performance
- [ ] **Test avec de gros volumes de données**
- [ ] **Test de la responsivité de l'interface**
- [ ] **Test de la gestion mémoire**

#### 6.3 Tests d'intégration Sonarr/Radarr
- [ ] **Test de l'auto-détection**
- [ ] **Test des scans déclenchés**
- [ ] **Test des configurations manuelles**

---

## 📊 SPÉCIFICATIONS TECHNIQUES DÉTAILLÉES

### Configuration Docker
```yaml
# Ajout dans docker compose.yml
volumes:
  - ./medias:/app/medias:rw
```

### Base de données
```sql
-- Table de configuration
CREATE TABLE symlink_config (
    id INTEGER PRIMARY KEY,
    media_path TEXT DEFAULT '/app/medias',
    max_workers INTEGER DEFAULT 6,
    sonarr_enabled BOOLEAN DEFAULT 0,
    sonarr_host TEXT,
    sonarr_port INTEGER,
    sonarr_api_key TEXT,
    radarr_enabled BOOLEAN DEFAULT 0,
    radarr_host TEXT,
    radarr_port INTEGER,
    radarr_api_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des scans (rotation des 3 derniers)
CREATE TABLE symlink_scans (
    id INTEGER PRIMARY KEY,
    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mode TEXT CHECK(mode IN ('dry-run', 'real')),
    selected_paths TEXT, -- JSON
    verification_depth TEXT CHECK(verification_depth IN ('basic', 'full')),
    total_analyzed INTEGER DEFAULT 0,
    phase1_ok INTEGER DEFAULT 0,
    phase1_broken INTEGER DEFAULT 0,
    phase1_inaccessible INTEGER DEFAULT 0,
    phase1_small INTEGER DEFAULT 0,
    phase1_io_error INTEGER DEFAULT 0,
    phase2_analyzed INTEGER DEFAULT 0,
    phase2_corrupted INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    duration REAL,
    status TEXT CHECK(status IN ('running', 'completed', 'cancelled', 'error')),
    results_json TEXT, -- Stockage temporaire
    error_message TEXT
);
```

### API Endpoints détaillés

#### Configuration
- **GET `/api/symlink/config`**
  - Retourne la configuration actuelle
  - Crée une config par défaut si inexistante

- **POST `/api/symlink/config`**
  - Sauvegarde la configuration
  - Validation des champs
  - Test des connexions si demandé

#### Scanner
- **GET `/api/symlink/directories`**
  - Parcourt `/app/medias`
  - Retourne l'arborescence avec compteurs de symlinks
  - Format : `{path, name, symlink_count, subdirs}`

- **POST `/api/symlink/scan/start`**
  - Paramètres : `{paths[], mode, verification_depth}`
  - Valide les paramètres
  - Lance le scan en arrière-plan
  - Retourne `{scan_id, status}`

- **GET `/api/symlink/scan/status/<scan_id>`**
  - Retourne le statut actuel du scan
  - Format : `{status, progress, phase, statistics, eta}`

#### Services
- **POST `/api/symlink/services/detect`**
  - Détecte automatiquement Sonarr/Radarr
  - Utilise `docker ps` et inspection des conteneurs
  - Retourne les configurations détectées

---

## ⚡ FONCTIONNALITÉS IMPLÉMENTÉES

### Scan en 2 phases (reproduit fidèlement le script original)
1. **Phase 1 - Vérification basique**
   - Liens cassés (cible inexistante)
   - Fichiers inaccessibles (permissions)
   - Fichiers vides (0 bytes)
   - Erreurs I/O (corruption système)

2. **Phase 2 - Vérification ffprobe**
   - Détection de corruption des fichiers médias
   - Validation de l'intégrité des conteneurs
   - Estimation du temps avant démarrage

### Modes d'exécution
- **Dry-run** : Détection seule, aucune suppression
- **Real** : Détection + suppression après confirmation utilisateur

### Intégration services média
- **Auto-détection Docker** : Scan automatique des conteneurs
- **Configuration manuelle** : Fallback avec test de connexion
- **Scans automatiques** : Déclenchement après nettoyage

### Gestion des données
- **Rapports temporaires** : Stockage en base pendant le scan
- **Historique rotatif** : Conservation des 3 derniers scans
- **Pas de sauvegarde** : Suppressions définitives selon les besoins

---

## 🔄 WORKFLOW D'UTILISATION

1. **Configuration initiale** (onglet Settings)
   - Définir le chemin des médias
   - Configurer Sonarr/Radarr si souhaité
   - Ajuster le nombre de workers

2. **Lancement d'un scan** (onglet Scanner)
   - Sélectionner les répertoires à analyser
   - Choisir le mode (dry-run pour test, real pour nettoyage)
   - Choisir la profondeur (basic rapide, full complet)
   - Démarrer et suivre la progression

3. **Analyse des résultats**
   - Consulter les statistiques
   - Examiner les problèmes détectés
   - Confirmer les suppressions en mode real

4. **Suivi** (onglet Dashboard)
   - Consulter l'historique des scans
   - Relancer des scans similaires
   - Surveiller l'état général

---

## ✅ CRITÈRES DE VALIDATION

### Fonctionnalité
- [ ] Reproduit exactement le comportement du script CLI
- [ ] Interface intuitive et cohérente avec Redriva
- [ ] Gestion asynchrone des tâches longues
- [ ] Configuration flexible via interface web

### Performance
- [ ] Pas de blocage de l'interface pendant les scans
- [ ] Gestion efficace de la mémoire
- [ ] Temps de réponse acceptables

### Sécurité
- [ ] Validation de tous les inputs utilisateur
- [ ] Confirmations pour les actions destructives
- [ ] Gestion propre des erreurs

### Évolutivité
- [ ] Base solide pour futurs outils similaires
- [ ] Code maintenable et documenté
- [ ] Architecture modulaire

---

## 📝 NOTES D'IMPLÉMENTATION

### Priorité des développements
1. **Critique** : Backend + modèles de données
2. **Important** : Interface Scanner avec progression temps réel
3. **Moyen** : Interface Settings et auto-détection
4. **Optionnel** : Optimisations et fonctionnalités avancées

### Points d'attention
- **Gestion mémoire** : Le script original peut traiter de gros volumes
- **Interruption propre** : Permettre l'arrêt sans corruption
- **Validation paths** : Sécuriser l'accès aux fichiers
- **Docker volumes** : Bien mapper les chemins entre host et container

### Extensibilité future
- Base préparée pour ajouter d'autres outils de maintenance
- Architecture réutilisable pour d'autres scripts CLI
- Possibilité d'ajouter des schedulers pour automatisation

---

**🎯 STATUS : PLAN COMPLET PRÊT POUR IMPLÉMENTATION**

*Ce plan servira de roadmap complète pour l'intégration du Symlink Manager dans Redriva, garantissant une intégration propre sans modification du code existant.*
