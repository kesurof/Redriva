# 🏗️ Redriva Web Architecture - Documentation Technique

Guide technique détaillé de l'architecture et du développement de l'interface web Redriva

## 📋 Table des Matières

1. [Architecture Générale](#-architecture-générale)
2. [Structure des Fichiers](#-structure-des-fichiers)
3. [Backend Flask](#-backend-flask)
4. [Frontend et Templates](#-frontend-et-templates)
5. [Base de Données](#-base-de-données)
6. [API et Endpoints](#-api-et-endpoints)
7. [Système de Logs](#-système-de-logs)
8. [Performance et Optimisation](#-performance-et-optimisation)
9. [Tests et Debugging](#-tests-et-debugging)
10. [Déploiement](#-déploiement)

---

## 🏛️ Architecture Générale

### Stack Technologique
```
┌─────────────────────────────────────┐
│           Frontend (Client)         │
│  HTML5 + CSS3 + Vanilla JavaScript │
│     Responsive + Interactive        │
└─────────────────────────────────────┘
                    │ HTTP/AJAX
┌─────────────────────────────────────┐
│          Backend (Server)           │
│        Python Flask 2.3+           │
│      Jinja2 Templates Engine        │
└─────────────────────────────────────┘
                    │ SQL
┌─────────────────────────────────────┐
│         Base de Données             │
│          SQLite 3.x                 │
│    Tables: torrents, torrent_details│
└─────────────────────────────────────┘
                    │ HTTP API
┌─────────────────────────────────────┐
│        Real-Debrid API              │
│      api.real-debrid.com            │
└─────────────────────────────────────┘
```

### Modèle MVC Adapté
```python
# Model : Accès aux données (main.py)
def get_db_stats():
    """Logique métier et accès BDD"""
    
# View : Templates Jinja2 (templates/*.html)  
def render_dashboard():
    """Présentation et interface utilisateur"""
    
# Controller : Routes Flask (web.py)
@app.route('/dashboard')
def dashboard():
    """Orchestration et logique de contrôle"""
```

---

## 📁 Structure des Fichiers

### Organisation du Projet Web
```
src/
├── web.py                 # 🎯 Serveur Flask principal
├── main.py               # 🔧 Logique métier et BDD
└── templates/            # 🎨 Templates Jinja2
    ├── base.html         # 📄 Template de base
    ├── dashboard.html    # 📊 Dashboard interactif
    ├── torrents.html     # 📋 Liste des torrents
    └── torrent_detail.html # 🔍 Détail d'un torrent

static/ (si créé)
├── css/
│   └── custom.css        # 🎨 Styles personnalisés
├── js/
│   └── app.js           # ⚡ JavaScript applicatif
└── img/
    └── favicon.ico      # 🖼️ Ressources graphiques

data/
├── redriva.db           # 💾 Base SQLite
└── webapp.log           # 📋 Logs spécifiques web
```

### Responsabilités par Fichier

#### `web.py` - Serveur Flask
```python
# Configuration Flask et routes principales
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Routes d'interface
@app.route('/')           # Dashboard principal
@app.route('/torrents')   # Liste des torrents
@app.route('/torrents/<id>') # Détail torrent

# Routes d'actions
@app.route('/sync/<type>') # Actions de synchronisation

# Routes API (pour AJAX)
@app.route('/api/stats')   # Statistiques JSON
```

#### `main.py` - Logique Métier
```python
# Constants pour cohérence
ACTIVE_STATUSES = (...)
ERROR_STATUSES = (...)

# Fonctions de statistiques pour le web
def show_stats_compact():
    """Stats pour dashboard"""

def get_smart_update_summary():
    """Analyse pour sync intelligent"""
```

#### `templates/` - Interface Utilisateur
```html
<!-- base.html : Structure commune -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{% block title %}Redriva{% endblock %}</title>
    <link rel="stylesheet" href="...">
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>

<!-- dashboard.html : Dashboard interactif -->
{% extends "base.html" %}
{% block content %}
<!-- Cartes statistiques, actions, logs -->
{% endblock %}
```

---

## 🐍 Backend Flask

### Configuration et Initialisation

#### Application Flask
```python
# web.py - Configuration principale
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Sécurité sessions

# Configuration pour développement
if __name__ == "__main__":
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🌐 Démarrage de l'interface web Redriva...")
    print(f"📱 URL: http://127.0.0.1:{port}")
    print(f"🛑 Utilisez Ctrl+C pour arrêter")
    
    app.run(host='127.0.0.1', port=port, debug=debug)
```

#### Gestion des Erreurs
```python
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404,
                         error_message="Page non trouvée"), 404

@app.errorhandler(500) 
def internal_error(error):
    return render_template('error.html',
                         error_code=500, 
                         error_message="Erreur interne du serveur"), 500
```

### Routes et Contrôleurs

#### Route Dashboard
```python
@app.route('/')
def dashboard():
    """Dashboard principal avec statistiques interactives"""
    try:
        # Import depuis main.py pour logique métier
        from main import (
            get_db_stats, 
            ACTIVE_STATUSES, 
            ERROR_STATUSES,
            load_token
        )
        
        # Récupération des statistiques
        total_torrents, total_details, coverage = get_db_stats()
        
        # Calcul des compteurs avec constantes standardisées
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Torrents actifs (utilisation des constantes)
        placeholders = ','.join('?' * len(ACTIVE_STATUSES))
        cursor.execute(f"""
            SELECT COUNT(*) FROM torrent_details 
            WHERE status IN ({placeholders})
        """, ACTIVE_STATUSES)
        active_count = cursor.fetchone()[0]
        
        # Torrents en erreur (utilisation des constantes)
        placeholders = ','.join('?' * len(ERROR_STATUSES))
        cursor.execute(f"""
            SELECT COUNT(*) FROM torrent_details 
            WHERE status IN ({placeholders})
        """, ERROR_STATUSES)
        error_count = cursor.fetchone()[0]
        
        # Autres statistiques...
        
        conn.close()
        
        # Passage des données au template
        return render_template('dashboard.html',
                             stats={
                                 'total_torrents': total_torrents,
                                 'total_details': total_details,
                                 'coverage': coverage,
                                 'active_count': active_count,
                                 'error_count': error_count,
                                 # ... autres stats
                             },
                             task_status={'running': False})
                             
    except Exception as e:
        logging.error(f"Erreur dashboard: {e}")
        return render_template('error.html', 
                             error_message="Erreur lors du chargement du dashboard")
```

#### Routes de Synchronisation
```python
@app.route('/sync/<sync_type>')
def sync_action(sync_type):
    """Exécution des actions de synchronisation"""
    try:
        token = load_token()
        
        # Mapping des types de sync
        sync_functions = {
            'smart': sync_smart,
            'fast': sync_all_v2, 
            'torrents': sync_torrents_only,
            'errors': lambda t: sync_details_only(t, 'error')
        }
        
        if sync_type not in sync_functions:
            return jsonify({'error': 'Type de synchronisation invalide'}), 400
            
        # Exécution de la synchronisation
        sync_function = sync_functions[sync_type]
        sync_function(token)
        
        return jsonify({
            'success': True,
            'message': f'Synchronisation {sync_type} terminée avec succès'
        })
        
    except Exception as e:
        logging.error(f"Erreur sync {sync_type}: {e}")
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500
```

### Intégration avec la Logique Métier

#### Séparation des Responsabilités
```python
# web.py - Interface et orchestration
@app.route('/torrents')
def torrents_list():
    # Logique de présentation et pagination
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    # Appel aux fonctions métier de main.py
    torrents_data = get_torrents_paginated(page, status_filter)
    
    return render_template('torrents.html', torrents=torrents_data)

# main.py - Logique métier et accès données  
def get_torrents_paginated(page=1, status_filter=None):
    """Récupération paginée avec filtres"""
    offset = (page - 1) * PAGE_SIZE
    
    query = "SELECT * FROM torrents"
    params = []
    
    if status_filter:
        query += " WHERE status = ?"
        params.append(status_filter)
        
    query += f" LIMIT {PAGE_SIZE} OFFSET {offset}"
    
    # Exécution et retour des données
    # ...
```

---

## 🎨 Frontend et Templates

### Structure des Templates Jinja2

#### Template de Base (`base.html`)
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Redriva Web{% endblock %}</title>
    
    <!-- CSS Bootstrap + Custom -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {% block styles %}{% endblock %}
    
    <!-- CSS inline pour composants spécialisés -->
    <style>
        /* Styles critiques inline pour performance */
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; 
        }
        /* ... autres styles critiques */
    </style>
</head>
<body>
    <!-- Navigation principale -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">🌐 Redriva Web</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/torrents">Torrents</a>
            </div>
        </div>
    </nav>
    
    <!-- Contenu principal -->
    <div class="container-fluid mt-4">
        {% block content %}{% endblock %}
    </div>
    
    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

#### Dashboard Interactif (`dashboard.html`)
```html
{% extends "base.html" %}

{% block title %}Dashboard - Redriva Web{% endblock %}

{% block content %}
<!-- System de notifications toast -->
<div id="toast-container" class="toast-container"></div>

<!-- Modal de confirmation -->
<div id="confirmModal" class="modal">
    <div class="modal-content">
        <h3 id="confirmTitle">Confirmer l'action</h3>
        <p id="confirmMessage">Êtes-vous sûr de vouloir effectuer cette action ?</p>
        <div class="modal-actions">
            <button id="confirmBtn" class="btn btn-primary">Confirmer</button>
            <button id="cancelBtn" class="btn">Annuler</button>
        </div>
    </div>
</div>

<!-- Cartes statistiques cliquables -->
<div class="stats-grid">
    {% for card in ['torrents', 'details', 'actifs', 'erreurs'] %}
    <div class="stat-card {{ card }} interactive" 
         onclick="navigateToSection('{{ card }}')"
         title="Cliquer pour voir {{ card }}">
        <!-- Contenu dynamique avec variables Jinja2 -->
        <div class="stat-icon">{{ card_icons[card] }}</div>
        <div class="stat-content">
            <h3>{{ card_titles[card] }}</h3>
            <h1>{{ stats[card + '_count']|default(0) }}</h1>
            <p>{{ card_descriptions[card] }}</p>
        </div>
        <div class="stat-arrow">→</div>
    </div>
    {% endfor %}
</div>

<!-- Actions de synchronisation -->
<div class="card action-card">
    <h2>🔄 Actions de synchronisation</h2>
    <div class="actions-grid">
        {% for action in sync_actions %}
        <button onclick="executeSyncAction('{{ action.url }}', '{{ action.name }}')" 
                class="action-btn {{ action.class }}">
            <div class="action-icon">{{ action.icon }}</div>
            <div class="action-content">
                <strong>{{ action.title }}</strong>
                <span>{{ action.description }}</span>
            </div>
        </button>
        {% endfor %}
    </div>
</div>

<!-- Console de logs interactive -->
<div class="card logs-card">
    <div class="logs-header">
        <h2>📋 Console d'activité</h2>
        <div class="logs-controls">
            <button onclick="toggleAutoScroll()" id="autoScrollBtn" class="btn btn-small">📌 Auto-scroll</button>
            <button onclick="clearLogs()" class="btn btn-small danger">🗑️ Effacer</button>
        </div>
    </div>
    
    <div id="logsContainer" class="logs-container">
        <div id="logsContent" class="logs-content">
            <div class="logs-placeholder">
                <div class="placeholder-icon">📝</div>
                <div class="placeholder-text">
                    <strong>Console prête</strong><br>
                    Les logs d'activité apparaîtront ici lors de l'exécution des actions.
                </div>
            </div>
        </div>
    </div>
</div>

{% endblock %}

{% block scripts %}
<script>
// JavaScript applicatif pour interactivité
// Fonctions de navigation, logs, modales, etc.
</script>
{% endblock %}
```

### JavaScript Applicatif

#### Système de Navigation
```javascript
// Navigation programmatique
function navigateToTorrents(status) {
    if (status) {
        window.location.href = `/torrents?status=${status}`;
    } else {
        window.location.href = '/torrents';
    }
}

// Navigation avec paramètres
function navigateToSection(section) {
    const routes = {
        'torrents': '/torrents',
        'actifs': '/torrents?status=downloading', 
        'erreurs': '/torrents?status=error',
        'details': '/dashboard#details-modal'
    };
    
    if (routes[section]) {
        window.location.href = routes[section];
    }
}
```

#### Système de Notifications
```javascript
// Toast notifications
function showToast(type, title, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <strong>${title}</strong><br>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Auto-remove après 5 secondes
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => container.removeChild(toast), 300);
    }, 5000);
}

// Types de notifications
showToast('success', 'Succès', 'Opération terminée');
showToast('error', 'Erreur', 'Problème rencontré');
showToast('info', 'Information', 'Action en cours');
showToast('warning', 'Attention', 'Vérification nécessaire');
```

#### AJAX et Actions Asynchrones
```javascript
// Exécution des synchronisations
function executeSyncAction(url, actionName) {
    // Modal de confirmation
    showConfirmModal(
        'Confirmer la synchronisation',
        `Voulez-vous vraiment lancer : ${actionName} ?`,
        () => {
            // Logs de début
            addLogEntry('info', `Démarrage de ${actionName}...`);
            showToast('info', 'Action lancée', `${actionName} en cours...`);
            
            // Requête AJAX
            fetch(url)
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    }
                    throw new Error(`HTTP ${response.status}`);
                })
                .then(data => {
                    // Succès
                    addLogEntry('success', `${actionName} terminée avec succès`);
                    showToast('success', 'Succès', `${actionName} terminée`);
                    
                    // Rechargement des statistiques
                    setTimeout(() => location.reload(), 2000);
                })
                .catch(error => {
                    // Erreur
                    addLogEntry('error', `Erreur lors de ${actionName}: ${error.message}`);
                    showToast('error', 'Erreur', `Échec de ${actionName}`);
                });
        }
    );
}
```

---

## 💾 Base de Données

### Schema SQLite

#### Tables Principales
```sql
-- Table des torrents (informations de base)
CREATE TABLE torrents (
    id TEXT PRIMARY KEY,           -- ID unique Real-Debrid
    filename TEXT,                 -- Nom du fichier/torrent
    status TEXT,                   -- Statut de base
    bytes INTEGER,                 -- Taille en bytes
    added_on TEXT                  -- Date d'ajout (ISO format)
);

-- Table des détails complets
CREATE TABLE torrent_details (
    id TEXT PRIMARY KEY,           -- FK vers torrents.id
    name TEXT,                     -- Nom complet
    status TEXT,                   -- Statut détaillé
    size INTEGER,                  -- Taille précise
    files_count INTEGER,           -- Nombre de fichiers
    progress INTEGER,              -- Progression 0-100
    links TEXT,                    -- Liens de téléchargement (CSV)
    hash TEXT,                     -- Hash du torrent
    host TEXT,                     -- Hébergeur
    error TEXT,                    -- Message d'erreur éventuel
    FOREIGN KEY (id) REFERENCES torrents (id)
);

-- Index pour performance
CREATE INDEX idx_torrents_status ON torrents(status);
CREATE INDEX idx_torrents_added ON torrents(added_on);
CREATE INDEX idx_details_status ON torrent_details(status);
```

### Requêtes Optimisées pour le Web

#### Statistiques Dashboard
```python
def get_dashboard_stats():
    """Récupération optimisée des statistiques pour dashboard"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Une seule requête complexe pour toutes les stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_torrents,
                COUNT(td.id) as total_details,
                ROUND(100.0 * COUNT(td.id) / COUNT(*), 1) as coverage,
                SUM(CASE WHEN td.status IN ('downloading', 'queued', 'waiting') 
                         THEN 1 ELSE 0 END) as active_count,
                SUM(CASE WHEN td.status IN ('error', 'timeout', 'dead') 
                         THEN 1 ELSE 0 END) as error_count,
                SUM(CASE WHEN datetime('now') - datetime(t.added_on) < 1 
                         THEN 1 ELSE 0 END) as recent_24h,
                SUM(t.bytes) as total_size
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
        """)
        
        return cursor.fetchone()
```

#### Pagination Efficace
```python
def get_torrents_paginated(page=1, status_filter=None, page_size=50):
    """Pagination avec comptage efficace"""
    offset = (page - 1) * page_size
    
    base_query = """
        SELECT t.*, td.status as detail_status, td.progress, td.error
        FROM torrents t
        LEFT JOIN torrent_details td ON t.id = td.id
    """
    
    count_query = "SELECT COUNT(*) FROM torrents t"
    where_clause = ""
    params = []
    
    if status_filter:
        where_clause = " WHERE COALESCE(td.status, t.status) = ?"
        params = [status_filter]
    
    # Requête de comptage
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(count_query + where_clause, params)
        total_count = cursor.fetchone()[0]
        
        # Requête des données paginées
        data_query = base_query + where_clause + f" LIMIT {page_size} OFFSET {offset}"
        cursor.execute(data_query, params)
        torrents = cursor.fetchall()
    
    return {
        'torrents': torrents,
        'page': page,
        'total_pages': (total_count + page_size - 1) // page_size,
        'total_count': total_count,
        'has_prev': page > 1,
        'has_next': page * page_size < total_count
    }
```

### Cache et Performance

#### Cache en Mémoire Simple
```python
import time
from functools import wraps

# Cache simple pour statistiques
_stats_cache = {}
CACHE_TTL = 30  # 30 secondes

def cached_stats(func):
    """Décorateur de cache pour les statistiques"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
        now = time.time()
        
        # Vérification du cache
        if cache_key in _stats_cache:
            cached_data, timestamp = _stats_cache[cache_key]
            if now - timestamp < CACHE_TTL:
                return cached_data
        
        # Calcul et mise en cache
        result = func(*args, **kwargs)
        _stats_cache[cache_key] = (result, now)
        return result
    
    return wrapper

@cached_stats
def get_dashboard_stats():
    """Statistiques avec cache automatique"""
    # ... logique de calcul
```

---

## 🔌 API et Endpoints

### Endpoints Web (HTML)

```python
# Routes principales d'interface
@app.route('/')                    # Dashboard principal
@app.route('/torrents')            # Liste des torrents
@app.route('/torrents/<id>')       # Détail d'un torrent  
@app.route('/search')              # Recherche
```

### Endpoints API (JSON)

```python
# API REST pour AJAX et intégrations
@app.route('/api/stats')
def api_stats():
    """Statistiques au format JSON"""
    stats = get_dashboard_stats()
    return jsonify({
        'total_torrents': stats[0],
        'total_details': stats[1], 
        'coverage': stats[2],
        'active_count': stats[3],
        'error_count': stats[4],
        'timestamp': time.time()
    })

@app.route('/api/torrents')
def api_torrents():
    """Liste des torrents au format JSON"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    
    data = get_torrents_paginated(page, status)
    
    return jsonify({
        'torrents': [dict(zip([col[0] for col in cursor.description], row)) 
                    for row in data['torrents']],
        'pagination': {
            'page': data['page'],
            'total_pages': data['total_pages'],
            'total_count': data['total_count'],
            'has_prev': data['has_prev'],
            'has_next': data['has_next']
        }
    })

@app.route('/api/sync/<sync_type>', methods=['POST'])
def api_sync(sync_type):
    """Déclenchement des synchronisations via API"""
    try:
        # Validation du type
        if sync_type not in ['smart', 'fast', 'torrents', 'errors']:
            return jsonify({'error': 'Type invalide'}), 400
            
        # Vérification qu'aucune sync n'est en cours
        if is_sync_running():
            return jsonify({'error': 'Synchronisation déjà en cours'}), 409
            
        # Lancement asynchrone
        threading.Thread(target=execute_sync, args=(sync_type,)).start()
        
        return jsonify({
            'success': True,
            'message': f'Synchronisation {sync_type} démarrée',
            'estimated_duration': get_estimated_duration(sync_type)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Gestion des Erreurs API

```python
@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Requête invalide'}), 400
    return render_template('error.html', error_code=400), 400

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erreur interne du serveur'}), 500
    return render_template('error.html', error_code=500), 500
```

---

## 📊 Système de Logs

### Configuration des Logs

```python
import logging
from logging.handlers import RotatingFileHandler

# Configuration spécifique pour l'interface web
def setup_web_logging():
    """Configuration des logs spécifiques à l'interface web"""
    
    # Logger principal
    web_logger = logging.getLogger('redriva.web')
    web_logger.setLevel(logging.INFO)
    
    # Handler fichier avec rotation
    file_handler = RotatingFileHandler(
        'data/webapp.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Format détaillé
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s'
    )
    file_handler.setFormatter(formatter)
    web_logger.addHandler(file_handler)
    
    # Handler console pour développement
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        web_logger.addHandler(console_handler)
    
    return web_logger

# Usage
web_logger = setup_web_logging()
```

### Types de Logs

```python
# Logs de navigation
@app.before_request
def log_request():
    """Log automatique des requêtes"""
    web_logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")

# Logs d'actions
@app.route('/sync/<sync_type>')
def sync_action(sync_type):
    web_logger.info(f"Sync action started: {sync_type} by {request.remote_addr}")
    try:
        # ... logique de sync
        web_logger.info(f"Sync action completed: {sync_type}")
    except Exception as e:
        web_logger.error(f"Sync action failed: {sync_type} - {str(e)}")

# Logs de performance
def log_performance(func):
    """Décorateur pour mesurer les performances"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        if elapsed > 1.0:  # Log si > 1 seconde
            web_logger.warning(f"Slow operation: {func.__name__} took {elapsed:.2f}s")
        
        return result
    return wrapper
```

### Monitoring et Métriques

```python
# Collecteur de métriques simple
class WebMetrics:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.sync_count = 0
        self.avg_response_time = 0
        self.start_time = time.time()
    
    def record_request(self, response_time):
        self.request_count += 1
        self.avg_response_time = (
            (self.avg_response_time * (self.request_count - 1) + response_time) 
            / self.request_count
        )
    
    def record_error(self):
        self.error_count += 1
    
    def record_sync(self):
        self.sync_count += 1
    
    def get_metrics(self):
        uptime = time.time() - self.start_time
        return {
            'uptime_seconds': uptime,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'sync_count': self.sync_count,
            'avg_response_time': self.avg_response_time,
            'requests_per_second': self.request_count / uptime if uptime > 0 else 0
        }

# Instance globale
metrics = WebMetrics()

# Endpoint de monitoring
@app.route('/api/metrics')
def api_metrics():
    """Métriques de performance du serveur web"""
    return jsonify(metrics.get_metrics())
```

---

## ⚡ Performance et Optimisation

### Optimisations Backend

#### Mise en Cache Intelligente
```python
from functools import lru_cache
import hashlib

# Cache LRU pour requêtes fréquentes
@lru_cache(maxsize=128)
def get_torrent_by_id(torrent_id):
    """Cache des torrents individuels"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, td.* FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE t.id = ?
        """, (torrent_id,))
        return cursor.fetchone()

# Cache avec invalidation sur modification
class CacheManager:
    def __init__(self):
        self._cache = {}
        self._cache_times = {}
    
    def get(self, key, ttl=300):
        """Récupération avec TTL"""
        if key in self._cache:
            if time.time() - self._cache_times[key] < ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_times[key]
        return None
    
    def set(self, key, value):
        """Mise en cache"""
        self._cache[key] = value
        self._cache_times[key] = time.time()
    
    def invalidate(self, pattern=None):
        """Invalidation par pattern"""
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
                del self._cache_times[key]
        else:
            self._cache.clear()
            self._cache_times.clear()

cache_manager = CacheManager()
```

#### Optimisation des Requêtes SQL
```python
# Requêtes précompilées pour performance
PREPARED_QUERIES = {
    'dashboard_stats': """
        SELECT 
            COUNT(*) as total,
            COUNT(td.id) as details,
            SUM(CASE WHEN td.status IN ('downloading', 'queued') THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN td.status = 'error' THEN 1 ELSE 0 END) as errors
        FROM torrents t LEFT JOIN torrent_details td ON t.id = td.id
    """,
    
    'torrents_paginated': """
        SELECT t.id, t.filename, t.status, t.bytes, td.progress, td.error
        FROM torrents t LEFT JOIN torrent_details td ON t.id = td.id
        ORDER BY t.added_on DESC LIMIT ? OFFSET ?
    """,
    
    'torrent_detail': """
        SELECT t.*, td.* FROM torrents t
        JOIN torrent_details td ON t.id = td.id
        WHERE t.id = ?
    """
}

def execute_prepared_query(query_name, params=None):
    """Exécution de requête précompilée"""
    if query_name not in PREPARED_QUERIES:
        raise ValueError(f"Unknown query: {query_name}")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row  # Accès par nom de colonne
        cursor = conn.cursor()
        cursor.execute(PREPARED_QUERIES[query_name], params or [])
        return cursor.fetchall()
```

### Optimisations Frontend

#### Lazy Loading et Pagination
```javascript
// Chargement progressif des torrents
class TorrentLoader {
    constructor(container, endpoint) {
        this.container = container;
        this.endpoint = endpoint;
        this.page = 1;
        this.loading = false;
        this.hasMore = true;
        
        this.setupInfiniteScroll();
    }
    
    setupInfiniteScroll() {
        window.addEventListener('scroll', () => {
            if (this.shouldLoadMore()) {
                this.loadMore();
            }
        });
    }
    
    shouldLoadMore() {
        const scrollHeight = document.documentElement.scrollHeight;
        const scrollTop = document.documentElement.scrollTop;
        const clientHeight = document.documentElement.clientHeight;
        
        return !this.loading && this.hasMore && 
               (scrollTop + clientHeight >= scrollHeight - 1000);
    }
    
    async loadMore() {
        if (this.loading || !this.hasMore) return;
        
        this.loading = true;
        this.showLoadingIndicator();
        
        try {
            const response = await fetch(`${this.endpoint}?page=${this.page}`);
            const data = await response.json();
            
            this.appendTorrents(data.torrents);
            this.hasMore = data.pagination.has_next;
            this.page++;
            
        } catch (error) {
            console.error('Erreur de chargement:', error);
            this.showError('Erreur lors du chargement des torrents');
        } finally {
            this.loading = false;
            this.hideLoadingIndicator();
        }
    }
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('torrents-container')) {
        new TorrentLoader('#torrents-container', '/api/torrents');
    }
});
```

#### Compression et Minification
```python
# Compression des réponses JSON
from flask import Flask
import gzip
import json

def gzip_response(data):
    """Compression GZIP des réponses JSON"""
    if request.headers.get('Accept-Encoding', '').find('gzip') != -1:
        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode('utf-8'))
        
        response = make_response(compressed)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Type'] = 'application/json'
        return response
    
    return jsonify(data)

# Usage dans les routes API
@app.route('/api/torrents')
def api_torrents():
    data = get_torrents_data()
    return gzip_response(data)
```

---

## 🧪 Tests et Debugging

### Tests Unitaires

```python
# tests/test_web.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web import app
import main

class TestWebInterface(unittest.TestCase):
    def setUp(self):
        """Configuration des tests"""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
    def test_dashboard_route(self):
        """Test de la route dashboard"""
        with patch('main.get_db_stats') as mock_stats:
            mock_stats.return_value = (100, 95, 95.0)
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Dashboard', response.data)
    
    def test_torrents_route(self):
        """Test de la route torrents"""
        response = self.client.get('/torrents')
        self.assertEqual(response.status_code, 200)
    
    def test_api_stats(self):
        """Test de l'API de statistiques"""
        with patch('main.get_db_stats') as mock_stats:
            mock_stats.return_value = (100, 95, 95.0)
            response = self.client.get('/api/stats')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('total_torrents', data)
    
    @patch('main.sync_smart')
    def test_sync_action(self, mock_sync):
        """Test des actions de synchronisation"""
        response = self.client.post('/sync/smart')
        self.assertEqual(response.status_code, 200)
        mock_sync.assert_called_once()

if __name__ == '__main__':
    unittest.main()
```

### Tests d'Intégration

```python
# tests/test_integration.py
import unittest
import tempfile
import os
import sqlite3
from web import app

class TestWebIntegration(unittest.TestCase):
    def setUp(self):
        """Configuration avec base de données temporaire"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.config['TESTING'] = True
        app.config['DATABASE'] = self.db_path
        self.client = app.test_client()
        
        # Créer les tables de test
        self.init_test_db()
    
    def tearDown(self):
        """Nettoyage"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def init_test_db(self):
        """Initialisation de la base de test"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Créer les tables et insérer des données de test
            cursor.execute("""
                CREATE TABLE torrents (
                    id TEXT PRIMARY KEY,
                    filename TEXT,
                    status TEXT,
                    bytes INTEGER,
                    added_on TEXT
                )
            """)
            # ... autres tables et données de test
    
    def test_full_workflow(self):
        """Test du workflow complet"""
        # 1. Charger le dashboard
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # 2. Naviguer vers les torrents
        response = self.client.get('/torrents')
        self.assertEqual(response.status_code, 200)
        
        # 3. Tester l'API
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
```

### Debugging et Monitoring

```python
# Middleware de debugging
@app.before_request
def debug_request():
    """Logs de debug pour les requêtes"""
    if app.debug:
        print(f"DEBUG: {request.method} {request.path}")
        print(f"DEBUG: Headers: {dict(request.headers)}")
        print(f"DEBUG: Args: {dict(request.args)}")

@app.after_request 
def debug_response(response):
    """Logs de debug pour les réponses"""
    if app.debug:
        print(f"DEBUG: Response {response.status_code}")
        print(f"DEBUG: Content-Type: {response.content_type}")
    return response

# Profiling des performances
import cProfile
import pstats
from functools import wraps

def profile_route(func):
    """Décorateur de profiling pour les routes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if app.config.get('PROFILE_ROUTES'):
            profiler = cProfile.Profile()
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()
            
            # Sauvegarder les stats
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumtime')
            stats.dump_stats(f'profile_{func.__name__}.prof')
        else:
            result = func(*args, **kwargs)
        
        return result
    return wrapper

# Usage
@app.route('/')
@profile_route
def dashboard():
    # ... logique du dashboard
```

---

## 🚀 Déploiement

### Configuration de Production

```python
# config/production.py
import os

class ProductionConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32)
    DEBUG = False
    TESTING = False
    
    # Base de données
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:///data/redriva.db'
    
    # Logging
    LOG_LEVEL = 'INFO' 
    LOG_FILE = 'logs/webapp.log'
    
    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 an pour les assets statiques
    
    # Sécurité
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

# web.py
def create_app(config_class=ProductionConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configuration du logging de production
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'], 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Redriva Web startup')
    
    return app
```

### Serveur WSGI (Gunicorn)

```bash
# requirements-prod.txt
gunicorn>=20.1.0
gevent>=21.12.0

# Installation
pip install -r requirements-prod.txt

# Lancement avec Gunicorn
gunicorn --workers 4 --bind 0.0.0.0:5000 --timeout 60 --keep-alive 2 web:app

# Avec configuration avancée
gunicorn --config gunicorn.conf.py web:app
```

```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
timeout = 60
keepalive = 2

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# Sécurité
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

### Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/redriva
server {
    listen 80;
    server_name redriva.local;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Assets statiques
    location /static {
        alias /path/to/redriva/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Logs
    access_log /var/log/nginx/redriva_access.log;
    error_log /var/log/nginx/redriva_error.log;
}
```

### Script de Déploiement

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Déploiement Redriva Web..."

# 1. Arrêter les services existants
./stop_web.sh 2>/dev/null || true

# 2. Mise à jour du code
git pull origin main

# 3. Installation des dépendances
pip install -r requirements.txt

# 4. Migration de la base de données (si nécessaire)
python src/main.py --migrate 2>/dev/null || true

# 5. Tests de base
python -m pytest tests/ --tb=short

# 6. Compilation des assets (si applicable)
# npm run build 2>/dev/null || true

# 7. Démarrage en production
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Avec Gunicorn
gunicorn --daemon --pid webapp.pid --bind 0.0.0.0:5000 web:app

echo "✅ Déploiement terminé!"
echo "🌐 Interface disponible sur http://localhost:5000"
```

### Monitoring et Maintenance

```python
# scripts/health_check.py
import requests
import sys
import json

def health_check():
    """Contrôle de santé de l'application"""
    try:
        # Test de la page d'accueil
        r = requests.get('http://localhost:5000/', timeout=10)
        if r.status_code != 200:
            print(f"❌ Dashboard inaccessible: HTTP {r.status_code}")
            return False
        
        # Test de l'API
        r = requests.get('http://localhost:5000/api/stats', timeout=10)
        if r.status_code != 200:
            print(f"❌ API inaccessible: HTTP {r.status_code}")
            return False
            
        stats = r.json()
        if 'total_torrents' not in stats:
            print("❌ API retourne des données invalides")
            return False
        
        print(f"✅ Application en ligne - {stats['total_torrents']} torrents")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur de connexion: {e}")
        return False
    except json.JSONDecodeError:
        print("❌ Réponse API invalide")
        return False

if __name__ == "__main__":
    success = health_check()
    sys.exit(0 if success else 1)
```

```bash
# Crontab pour monitoring automatique
# crontab -e
*/5 * * * * /path/to/redriva/scripts/health_check.py || /path/to/redriva/restart_web.sh
```

---

## 📝 Conclusion

Cette documentation technique couvre tous les aspects de l'architecture et du développement de l'interface web Redriva. Elle sert de référence pour :

- **Développeurs** : Compréhension de l'architecture et contribution
- **Administrateurs** : Déploiement et maintenance
- **Utilisateurs avancés** : Personnalisation et extension

### Points Clés à Retenir

1. **Architecture MVC adaptée** avec séparation claire des responsabilités
2. **Performance optimisée** via cache, pagination et requêtes efficaces  
3. **Interface moderne** avec composants interactifs et responsive design
4. **API REST** pour intégrations et développements futurs
5. **Monitoring intégré** avec logs, métriques et health checks
6. **Déploiement simplifié** avec scripts automatisés et configuration de production

### Évolutions Futures

L'architecture actuelle est conçue pour supporter :
- Montée en charge utilisateurs
- Nouvelles fonctionnalités (WebSocket, notifications push)
- Intégrations tierces via API
- Personnalisation avancée (thèmes, plugins)

---

*Documentation technique maintenue par l'équipe Redriva*  
*Version : 2.0 - Juillet 2025*
