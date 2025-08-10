#!/usr/bin/env python3
"""
Redriva - Synchroniseur Real-Debrid
====================================
Outil de synchronisation Python pour archiver vos torrents Real-Debrid 
dans une base de données SQLite locale.

Maintenu via Claude/Copilot - Architecture monolithique organisée

TABLE DES MATIÈRES:
==================
1. IMPORTS ET CONFIGURATION          (lignes 1-80)
2. UTILITAIRES ET HELPERS           (lignes 81-150)  
3. BASE DE DONNÉES                  (lignes 151-220)
4. API REAL-DEBRID                  (lignes 221-400)
5. SYNCHRONISATION                  (lignes 401-700)
6. STATISTIQUES ET ANALYTICS        (lignes 701-850)
7. DIAGNOSTIC ET MAINTENANCE        (lignes 851-950)
8. INTERFACE UTILISATEUR (MENU)     (lignes 951-1100)
9. POINT D'ENTRÉE PRINCIPAL         (lignes 1100+)

Fonctionnalités principales:
- 🔄 Synchronisation intelligente avec modes optimisés
- 📊 Statistiques complètes et analytics avancées  
- 🔍 Diagnostic automatique des erreurs
- 🎮 Menu interactif convivial
- ⚡ Performance optimisée avec contrôle dynamique
"""

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                         SECTION 1: IMPORTS ET CONFIGURATION                ║
# ╚════════════════════════════════════════════════════════════════════════════╝

import os
import sys
import argparse
import asyncio
import aiohttp
import sqlite3
import time
import signal
import logging
import json
import re
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE STATUTS POUR COHÉRENCE DANS TOUT LE CODE
# ═══════════════════════════════════════════════════════════════════════════════

# Statuts considérés comme "actifs" (torrents en cours de traitement)
ACTIVE_STATUSES = (
    'downloading',           # ⬇️ En cours de téléchargement
    'queued',               # 🔄 En file d'attente
    'waiting_files_selection', # ⏳ En attente de sélection des fichiers
    'magnet_conversion',    # 🧲 Conversion magnet en cours
    'uploading',            # ⬆️ Upload en cours
    'compressing',          # 🗜️ Compression en cours
    'waiting'               # ⏳ En attente générique
)

# Statuts considérés comme "erreurs" (problèmes nécessitant intervention)
ERROR_STATUSES = (
    'error',                # ❌ Erreur générique
    'magnet_error',         # 🧲❌ Erreur de magnet
    'virus',                # 🦠 Fichier infecté
    'dead',                 # 💀 Torrent mort
    'timeout',              # ⏱️ Timeout
    'hoster_unavailable'    # 🚫 Hébergeur indisponible
)

# Statuts considérés comme "terminés" (téléchargements réussis)
COMPLETED_STATUSES = (
    'downloaded',           # ✅ Téléchargé avec succès
    'finished'              # 🏁 Terminé
)

# Tous les statuts connus (pour validation)
ALL_KNOWN_STATUSES = ACTIVE_STATUSES + ERROR_STATUSES + COMPLETED_STATUSES


# Configuration du logging avec format enrichi
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING STRUCTURE : helper pour événements parsables dans docker logs
# Convention : lignes commençant par [SYNC_*] / [DETAILS_*] / [CLEAN_*]
# Format : [TAG key=value key2=value2 ...] (valeurs sans espaces, ou entre guillemets)
# Objectif : permettre grep/awk facile (ex: grep '^\[SYNC_END').
# ──────────────────────────────────────────────────────────────────────────────
def log_event(tag: str, **fields):
    """Émet une ligne de log structurée parsable.

    Args:
        tag (str): Nom d'événement (ex: SYNC_START, SYNC_END, DETAILS_PROGRESS)
        **fields: Paires clé=valeur (sans transformation). Les valeurs contenant
                  des espaces ou '=' seront entourées de guillemets doubles.
    """
    parts = []
    for k, v in fields.items():
        if v is None:
            continue
        val = str(v)
        if ' ' in val or '=' in val:
            val = '"' + val.replace('"', "'") + '"'
        parts.append(f"{k}={val}")
    line = f"[{tag} {' '.join(parts)}]" if parts else f"[{tag}]"
    # Utilise logging.info pour rester homogène avec le reste
    logging.info(line)

# Gestion de l'interruption propre (CTRL+C)
stop_requested = False
def handle_sigint(signum, frame):
    """Gestionnaire d'interruption propre pour éviter la corruption de données"""
    global stop_requested
    logging.warning("Interruption clavier reçue (CTRL+C), arrêt propre...")
    stop_requested = True

signal.signal(signal.SIGINT, handle_sigint)

# Configuration via gestionnaire centralisé
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config_manager import get_config

# Configuration avec nouvelles valeurs centralisées
RD_API_URL = "https://api.real-debrid.com/rest/1.0/torrents"

# Fonction pour obtenir le chemin de la base de données
def get_db_path():
    """Récupère le chemin de la base de données via le gestionnaire de configuration"""
    config = get_config()
    return config.get_db_path()

# Utilisation du gestionnaire de configuration pour les paramètres
config = get_config()
MAX_CONCURRENT = config.get('realdebrid.max_concurrent', 50)
BATCH_SIZE = config.get('realdebrid.batch_size', 250)
QUOTA_WAIT_TIME = config.get('realdebrid.quota_wait', 60)
TORRENT_QUOTA_WAIT = config.get('realdebrid.torrent_wait', 10)
PAGE_WAIT_TIME = config.get('realdebrid.page_wait', 1.0)

# DB_PATH sera initialisé dynamiquement via get_db_path()
DB_PATH = get_db_path()

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                         SECTION 2: UTILITAIRES ET HELPERS                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def format_size(bytes_size):
    """
    Convertit les bytes en format lisible (KB, MB, GB, TB)
    
    Args:
        bytes_size (int): Taille en bytes
        
    Returns:
        str: Taille formatée avec unité appropriée
        
    Example:
        >>> format_size(1536000000)
        '1.4 GB'
    """
    if bytes_size is None:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"

def get_status_emoji(status):
    """
    Retourne un emoji représentatif selon le statut du torrent
    
    Args:
        status (str): Statut du torrent
        
    Returns:
        str: Emoji correspondant au statut
    """
    status_emojis = {
        'downloaded': '✅',      # Téléchargement terminé
        'downloading': '⬇️',     # En cours de téléchargement
        'waiting': '⏳',         # En attente
        'queued': '🔄',          # En file d'attente
        'error': '❌',           # Erreur
        'magnet_error': '🧲❌',   # Erreur magnet
        'magnet_conversion': '🧲', # Conversion magnet
        'virus': '🦠',           # Virus détecté
        'dead': '💀',            # Torrent mort
        'uploading': '⬆️',       # Upload en cours
        'compressing': '🗜️'      # Compression en cours
    }
    return status_emojis.get(status, '❓')

def safe_int(value, default=0):
    """
    Conversion sécurisée en entier
    
    Args:
        value: Valeur à convertir
        default (int): Valeur par défaut si conversion impossible
        
    Returns:
        int: Valeur convertie ou valeur par défaut
    """
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """
    Conversion sécurisée en float
    
    Args:
        value: Valeur à convertir
        default (float): Valeur par défaut si conversion impossible
        
    Returns:
        float: Valeur convertie ou valeur par défaut
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                           SECTION 3: BASE DE DONNÉES                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def create_tables():
    """
    Initialise la base de données SQLite avec les tables nécessaires
    
    Tables créées:
    - torrents: Informations de base des torrents
    - torrent_details: Détails complets des torrents
    - sync_progress: Progression des synchronisations (pour reprise)
    """
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Table principale des torrents (informations de base)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS torrents (
            id TEXT PRIMARY KEY,
            filename TEXT,
            status TEXT,
            bytes INTEGER,
            added_on TEXT
        )
    ''')
    
    # Table des détails complets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS torrent_details (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            size INTEGER,
            files_count INTEGER,
            progress INTEGER,
            links TEXT,
            streaming_links TEXT,
            hash TEXT,
            host TEXT,
            error TEXT,
            added TEXT,
            FOREIGN KEY (id) REFERENCES torrents (id)
        )
    ''')
    
    # Table pour la reprise des synchronisations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_progress (
            id INTEGER PRIMARY KEY,
            operation TEXT,
            total_items INTEGER,
            processed_items INTEGER,
            last_processed_id TEXT,
            start_time TEXT,
            status TEXT
        )
    ''')
    
    # Ajouter la nouvelle colonne health_error si elle n'existe pas
    try:
        cursor.execute("ALTER TABLE torrent_details ADD COLUMN health_error TEXT")
        logging.info("✅ Colonne health_error ajoutée à torrent_details")
    except sqlite3.OperationalError:
        # La colonne existe déjà
        pass
    
    # Index pour optimiser les performances
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_torrents_status ON torrents(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_torrents_added ON torrents(added_on)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_details_status ON torrent_details(status)')
    
    conn.commit()
    conn.close()
    logging.info("Base de données initialisée avec succès")

def get_db_stats():
    """
    Récupère les statistiques de base de la base de données
    
    Returns:
        tuple: (total_torrents, total_details, coverage_percent)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Compte total des torrents
    cursor.execute("SELECT COUNT(*) FROM torrents")
    total_torrents = cursor.fetchone()[0]
    
    # Compte des détails disponibles
    cursor.execute("SELECT COUNT(*) FROM torrent_details")
    total_details = cursor.fetchone()[0]
    
    conn.close()
    
    coverage = (total_details / total_torrents * 100) if total_torrents > 0 else 0
    return total_torrents, total_details, coverage

def clear_database():
    """
    Vide complètement la base de données après confirmation
    
    Supprime toutes les données des tables tout en conservant la structure.
    Opération irréversible, demande confirmation explicite.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM torrent_details")
    cursor.execute("DELETE FROM torrents")
    
    # Reset des compteurs auto-increment seulement si la table existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    if cursor.fetchone():
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('torrents', 'torrent_details')")
    
    conn.commit()
    conn.close()
    
    logging.info("Base de données vidée avec succès")
    print("✅ Base de données complètement vidée")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                           SECTION 4: API REAL-DEBRID                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def load_token():
    """
    Récupère le token Real-Debrid depuis la configuration centralisée
    Gère tous les cas d'erreurs possibles pour éviter Header Injection
    
    Source: Configuration centralisée (config.json) ou variables d'environnement
    
    Returns:
        str: Token Real-Debrid valide et nettoyé
        
    Raises:
        SystemExit: Si aucun token valide trouvé
    """
    import re
    
    def clean_token(raw_token):
        """Nettoie un token de tous les caractères parasites"""
        if not raw_token:
            return None
            
        # Étape 1 : Conversion en string et suppression des espaces
        token = str(raw_token).strip()
        
        # Étape 2 : Suppression de tous les caractères de contrôle
        token = re.sub(r'[\r\n\t\f\v]', '', token)
        
        # Étape 3 : Suppression des espaces multiples
        token = re.sub(r'\s+', '', token)
        
        # Étape 4 : Validation format (seuls alphanumériques, tirets, underscores)
        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            return None
            
        # Étape 5 : Validation longueur (tokens RD font généralement 40-60 caractères)
        if len(token) < 30 or len(token) > 80:
            return None
            
        return token
    
    # Priorité 1: Variable d'environnement (Docker/Système)
    env_token = os.getenv('RD_TOKEN')
    if env_token:
        cleaned = clean_token(env_token)
        if cleaned:
            logging.info("🔑 Token chargé depuis variable d'environnement")
            return cleaned
        else:
            logging.warning("⚠️ Token d'environnement invalide")
    
    # Priorité 2: Configuration centralisée (config.json)
    config = get_config()
    config_token = config.get_token()
    if config_token:
        cleaned = clean_token(config_token)
        if cleaned:
            logging.info("🔑 Token chargé depuis configuration centralisée")
            return cleaned
        else:
            logging.warning("⚠️ Token de configuration invalide")
    
    # Priorité 3: Ancien fichier token pour compatibilité
    try:
        token_paths = [
            os.path.join(os.path.dirname(__file__), '../data/token'),
            os.path.join(os.path.dirname(__file__), '../config/token'),
            '/app/data/token'
        ]
        
        for token_path in token_paths:
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    file_token = f.read().strip()
                    cleaned = clean_token(file_token)
                    if cleaned:
                        logging.info(f"🔑 Token chargé depuis fichier: {token_path}")
                        # Migrer vers la configuration centralisée
                        config.update_config('realdebrid.token', cleaned)
                        logging.info("🔄 Token migré vers configuration centralisée")
                        return cleaned
                    else:
                        logging.warning(f"⚠️ Token du fichier {token_path} invalide")
                        
    except Exception as e:
        logging.warning(f"⚠️ Erreur lecture fichier token: {e}")
    
    # Aucun token valide trouvé
    print("\n❌ ERREUR: Aucun token Real-Debrid valide trouvé")
    print("\n📋 Solutions possibles:")
    print("   1. Variable d'environnement: export RD_TOKEN='votre_token'")
    print("   2. Configuration centralisée: modifier config/config.json")
    print("   3. Interface web: aller dans Paramètres > Real-Debrid")
    print("\n🔗 Obtenir votre token: https://real-debrid.com/apitoken")
    
    sys.exit(1)

async def api_request(session, url, headers, params=None, max_retries=3):
    """
    Fonction générique pour les appels API Real-Debrid avec gestion d'erreurs complète
    
    Features:
    - Retry automatique avec backoff exponentiel
    - Gestion des quotas API (429)
    - Gestion des erreurs d'authentification
    - Support interruption propre (CTRL+C)
    
    Args:
        session: Session aiohttp
        url (str): URL de l'API
        headers (dict): Headers incluant l'authentification
        params (dict, optional): Paramètres de requête
        max_retries (int): Nombre maximum de tentatives
        
    Returns:
        dict/None: Réponse JSON ou None en cas d'erreur
    """
    for attempt in range(max_retries):
        if stop_requested:
            return None
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                # Gestion des erreurs d'authentification
                if resp.status == 401 or resp.status == 403:
                    logging.error("Token Real-Debrid invalide ou expiré.")
                    sys.exit(1)
                
                # Torrent non trouvé (normal dans certains cas)
                if resp.status == 404:
                    return None
                
                # Gestion du quota API
                if resp.status == 429:
                    wait_time = QUOTA_WAIT_TIME if params else TORRENT_QUOTA_WAIT
                    logging.warning(f"Quota API dépassé, attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                resp.raise_for_status()
                return await resp.json()
                
        except Exception as e:
            if attempt == max_retries - 1:
                logging.error(f"Erreur API après {max_retries} tentatives: {e}")
                return None
            # Backoff exponentiel
            await asyncio.sleep(2 ** attempt)
    return None

async def fetch_all_torrents(token):
    """
    Récupère tous les torrents depuis l'API Real-Debrid avec temporisation adaptative
    
    Utilise la pagination pour récupérer tous les torrents par batches de 2500.
    Sauvegarde directement en base pour éviter la surcharge mémoire.
    Temporisation adaptative selon les erreurs détectées.
    
    Args:
        token (str): Token d'authentification Real-Debrid
        
    Returns:
        int: Nombre total de torrents récupérés
    """
    headers = {"Authorization": f"Bearer {token}"}
    limit = 5000
    page = 1
    total = 0
    
    # Variables pour la temporisation adaptative
    page_wait = PAGE_WAIT_TIME  # Utilise la constante définie
    consecutive_errors = 0
    
    async with aiohttp.ClientSession() as session:
        while True:
            if stop_requested:
                logging.info("Arrêt demandé, interruption de la récupération des torrents.")
                break
                
            params = {"page": page, "limit": limit}
            
            try:
                # Appel API avec gestion d'erreurs
                torrents = await api_request(session, RD_API_URL, headers, params)
                
                if not torrents:
                    break
                
                # ✅ Succès - Reset du compteur d'erreurs
                consecutive_errors = 0
                
                # Sauvegarde immédiate en base
                for t in torrents:
                    upsert_torrent(t)
                    
                total += len(torrents)
                logging.info(f"📄 Page {page}: {len(torrents)} torrents ({total} total)")
                page += 1
                
                # 🎯 TEMPORISATION ADAPTATIVE
                if len(torrents) == limit:  # S'il y a encore des pages
                    if consecutive_errors > 0:
                        # Pause plus longue si des erreurs ont été détectées récemment
                        adaptive_wait = page_wait * (1 + consecutive_errors * 0.5)
                        logging.info(f"⏸️ Pause adaptative {adaptive_wait:.1f}s (après {consecutive_errors} erreurs)")
                        await asyncio.sleep(adaptive_wait)
                        consecutive_errors = 0  # Reset après pause adaptative
                    else:
                        # Pause normale
                        await asyncio.sleep(page_wait)
                        logging.info(f"⏸️ Pause normale {page_wait}s")
                
            except Exception as e:
                # ❌ Erreur détectée - Incrémenter le compteur
                consecutive_errors += 1
                logging.warning(f"⚠️ Erreur page {page} (tentative {consecutive_errors}): {e}")
                
                # Pause immédiate adaptative en cas d'erreur
                error_wait = page_wait * (1 + consecutive_errors * 0.5)
                logging.info(f"⏸️ Pause d'erreur {error_wait:.1f}s...")
                await asyncio.sleep(error_wait)
                
                # Ne pas incrémenter page - retry la même page
                continue
                
    return total

async def fetch_torrent_detail(session, token, torrent_id):
    """
    Récupère les détails complets d'un torrent spécifique
    
    Args:
        session: Session aiohttp
        token (str): Token d'authentification
        torrent_id (str): ID du torrent
        
    Returns:
        dict/None: Détails du torrent ou None si erreur
    """
    url = f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    detail = await api_request(session, url, headers)
    if detail:
        logging.debug(f"Détail récupéré pour {torrent_id}")
        upsert_torrent_detail(detail)
    return detail

def upsert_torrent(t):
    """
    Insert ou met à jour un torrent dans la table torrents
    
    Args:
        t (dict): Données du torrent depuis l'API
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO torrents (id, filename, status, bytes, added_on)
            VALUES (?, ?, ?, ?, ?)''',
            (t.get('id'), t.get('filename'), t.get('status'), t.get('bytes'), t.get('added'))
        )
        conn.commit()

def upsert_torrent_detail(detail):
    """
    Insert ou met à jour les détails d'un torrent dans la table torrent_details
    
    Args:
        detail (dict): Détails du torrent depuis l'API
    """
    if not detail or not detail.get('id'):
        return
        
    # Extraire les liens de téléchargement et de streaming
    download_links = []
    streaming_links = []
    
    # Parcourir les fichiers du torrent
    files = detail.get('files', [])
    for file_info in files:
        # Lien de téléchargement
        download_link = file_info.get('link', '')
        if download_link:
            download_links.append(download_link)
        
        # Lien de streaming - plusieurs champs possibles selon l'API Real-Debrid
        streaming_link = (
            file_info.get('streamable_link') or 
            file_info.get('streaming_link') or 
            file_info.get('stream_link') or
            file_info.get('alternative_link') or
            ''
        )
        streaming_links.append(streaming_link)
    
    # Si pas de fichiers, utiliser l'ancien format (liste de liens directe)
    if not files and detail.get('links'):
        download_links = detail.get('links', [])
        # Pour l'ancien format, on ne peut pas deviner les liens de streaming
        streaming_links = [''] * len(download_links)
        
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Récupérer le health_error existant pour le préserver
        c.execute('SELECT health_error FROM torrent_details WHERE id = ?', (detail.get('id'),))
        existing_health_error = c.fetchone()
        preserved_health_error = existing_health_error[0] if existing_health_error else None
        
        c.execute('''INSERT OR REPLACE INTO torrent_details
            (id, name, status, size, files_count, progress, links, streaming_links, hash, host, error, added, health_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                detail.get('id'),
                detail.get('filename') or detail.get('name'),
                detail.get('status'),
                detail.get('bytes'),
                len(detail.get('files', [])),
                detail.get('progress'),
                ",".join(download_links) if download_links else None,
                ",".join(streaming_links) if streaming_links else None,
                detail.get('hash'),
                detail.get('host'),
                detail.get('error'),
                detail.get('added'),
                preserved_health_error  # Préserver le health_error existant
            )
        )
        conn.commit()

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                         SECTION 5: SYNCHRONISATION                        ║  
# ╚════════════════════════════════════════════════════════════════════════════╝

class DynamicRateLimiter:
    """
    Contrôleur dynamique de concurrence pour optimiser les performances API
    
    Ajuste automatiquement le nombre de requêtes simultanées selon:
    - Taux de succès/échec
    - Performance générale
    - Respect des quotas API
    
    Attributes:
        concurrent (int): Nombre actuel de requêtes simultanées
        max_concurrent (int): Limite maximale
        success_count (int): Compteur de succès
        error_count (int): Compteur d'erreurs
    """
    
    def __init__(self, initial_concurrent=20, max_concurrent=80):
        self.concurrent = initial_concurrent
        self.max_concurrent = max_concurrent
        self.success_count = 0
        self.error_count = 0
        self.last_adjustment = time.time()
        
    def adjust_concurrency(self, success=True):
        """
        Ajuste la concurrence selon les résultats
        
        Args:
            success (bool): True si la dernière requête a réussi
        """
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            
        # Ajustement périodique ou après un seuil
        if (self.success_count + self.error_count) % 50 == 0 or time.time() - self.last_adjustment > 30:
            error_rate = self.error_count / max(1, self.success_count + self.error_count)
            
            # Augmenter si peu d'erreurs
            if error_rate < 0.05:
                self.concurrent = min(self.max_concurrent, int(self.concurrent * 1.2))
                logging.info(f"📈 Concurrence augmentée à {self.concurrent}")
            # Réduire si trop d'erreurs
            elif error_rate > 0.15:
                self.concurrent = max(5, int(self.concurrent * 0.7))
                logging.info(f"📉 Concurrence réduite à {self.concurrent}")
                
            self.last_adjustment = time.time()
            self.success_count = self.error_count = 0
            
    def get_semaphore(self):
        """Retourne un semaphore avec la concurrence actuelle"""
        return asyncio.Semaphore(self.concurrent)

def save_progress(processed_ids, filename="data/sync_progress.json"):
    """
    Sauvegarde la progression d'une synchronisation pour reprise ultérieure
    
    Args:
        processed_ids (set): IDs des torrents déjà traités
        filename (str): Chemin du fichier de sauvegarde
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        json.dump({
            'processed_ids': list(processed_ids),
            'timestamp': time.time()
        }, f)

def load_progress(filename="data/sync_progress.json"):
    """
    Charge la progression d'une synchronisation précédente
    
    Args:
        filename (str): Chemin du fichier de sauvegarde
        
    Returns:
        set: IDs des torrents déjà traités (max 6h d'ancienneté)
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            # Ignorer si plus de 6 heures
            if time.time() - data['timestamp'] < 21600:
                return set(data['processed_ids'])
    except:
        pass
    return set()

async def fetch_all_torrent_details_v2(token, torrent_ids, resumable=False):
    """
    Version optimisée pour récupérer les détails de torrents (sync-fast et sync-smart)
    
    Features:
    - Contrôle dynamique de la concurrence
    - Reprise possible des synchronisations interrompues
    - Pool de connexions optimisé
    - Statistiques temps réel
    - Sauvegarde progressive
    
    Args:
        token (str): Token Real-Debrid
        torrent_ids (list): Liste des IDs à traiter
        resumable (bool): Si True, permet la reprise
        
    Returns:
        int: Nombre de détails traités avec succès
    """
    # Gestion de la reprise
    if resumable:
        processed_ids = load_progress()
        remaining_ids = [tid for tid in torrent_ids if tid not in processed_ids]
        if processed_ids:
            logging.info(f"📂 Reprise: {len(processed_ids)} déjà traités, {len(remaining_ids)} restants")
    else:
        remaining_ids = torrent_ids
        processed_ids = set()
    
    if not remaining_ids:
        logging.info("✅ Tous les détails sont à jour !")
        return len(processed_ids)
    
    rate_limiter = DynamicRateLimiter()
    total_processed = len(processed_ids)
    start_time = time.time()
    
    # Pool de connexions optimisé
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50, keepalive_timeout=30)
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        
        async def process_torrent_optimized(tid):
            """Traite un torrent avec contrôle de concurrence dynamique"""
            semaphore = rate_limiter.get_semaphore()
            async with semaphore:
                result = await fetch_torrent_detail(session, token, tid)
                success = result is not None
                rate_limiter.adjust_concurrency(success)
                
                if success:
                    nonlocal total_processed
                    total_processed += 1
                    processed_ids.add(tid)
                    
                    # Stats temps réel + sauvegarde périodique
                    if total_processed % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = (total_processed - len(processed_ids)) / elapsed if elapsed > 0 else 0
                        remaining = len(torrent_ids) - total_processed
                        eta = remaining / rate if rate > 0 else 0
                        
                        logging.info(f"📊 {total_processed}/{len(torrent_ids)} | "
                                   f"{rate:.1f}/s | ETA: {eta/60:.1f}min | "
                                   f"Concurrence: {rate_limiter.concurrent}")
                        
                        if resumable:
                            save_progress(processed_ids)
                
                return result
        
        # Traitement par chunks adaptatifs
        chunk_size = min(300, len(remaining_ids))
        for i in range(0, len(remaining_ids), chunk_size):
            if stop_requested:
                break
                
            chunk_ids = remaining_ids[i:i+chunk_size]
            tasks = [process_torrent_optimized(tid) for tid in chunk_ids]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Pause adaptative entre chunks
            if i + chunk_size < len(remaining_ids):
                pause = max(3, 20 - rate_limiter.concurrent * 0.2)
                logging.info(f"⏸️  Pause {pause:.1f}s...")
                await asyncio.sleep(pause)
    
    elapsed = time.time() - start_time
    processed_new = total_processed - len(set(processed_ids) - processed_ids)
    logging.info(f"🎉 Terminé ! {processed_new} nouveaux détails en {elapsed/60:.1f}min "
                 f"({processed_new/elapsed:.1f} torrents/s)")
    
    # Nettoyer le fichier de progression si terminé
    if resumable and os.path.exists("data/sync_progress.json"):
        os.remove("data/sync_progress.json")
    
    return total_processed

def get_smart_update_summary():
    """
    Analyse intelligente des torrents nécessitant une mise à jour
    
    Catégories analysées:
    - Nouveaux torrents sans détails
    - Téléchargements actifs
    - Torrents en erreur (retry)
    - Torrents anciens (>7 jours)
    
    Returns:
        dict: Résumé des changements détectés
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Nouveaux torrents (pas de détails)
        c.execute('''
            SELECT COUNT(*) FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE td.id IS NULL
        ''')
        new_count = c.fetchone()[0]
        
        # Téléchargements actifs (utilisation des constantes)
        placeholders = ','.join('?' * len(ACTIVE_STATUSES))
        c.execute(f'''
            SELECT COUNT(*) FROM torrent_details
            WHERE status IN ({placeholders})
        ''', ACTIVE_STATUSES)
        active_count = c.fetchone()[0]
        
        # Torrents en erreur (pour retry) - utilisation des constantes d'erreur
        placeholders = ','.join('?' * len(ERROR_STATUSES))
        c.execute(f'''
            SELECT COUNT(*) FROM torrent_details
            WHERE status IN ({placeholders}) OR error IS NOT NULL
        ''', ERROR_STATUSES)
        error_count = c.fetchone()[0]
        
        # Torrents anciens (plus de 7 jours sans mise à jour)
        c.execute('''
            SELECT COUNT(*) FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE datetime('now') - datetime(t.added_on) > 7
        ''')
        old_count = c.fetchone()[0]
        
        return {
            'new_torrents': new_count,
            'active_downloads': active_count,
            'error_retry': error_count,
            'old_updates': old_count
        }

def get_torrents_needing_update():
    """
    Identifie les torrents nécessitant une mise à jour pour sync-smart
    
    Critères:
    - Nouveaux torrents sans détails
    - Téléchargements actifs (downloading, queued, etc.)
    - Torrents en erreur (retry automatique)
    - Torrents anciens (>7 jours)
    
    Returns:
        list: Liste des IDs de torrents à mettre à jour
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT t.id FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE td.id IS NULL 
               OR (td.status IN ('downloading', 'queued', 'waiting_files_selection'))
               OR (td.status = 'error' OR td.error IS NOT NULL)
               OR datetime('now') - datetime(t.added_on) > 7
        ''')
        return [row[0] for row in c.fetchall()]

def sync_smart(token):
    """
    Synchronisation intelligente optimisée - Mode recommandé pour usage quotidien
    
    Logique en 3 phases optimisées :
    1. 🚀 PHASE 1 : Mise à jour ultra-rapide des statuts via torrents_only (10-30s)
    2. 🎯 PHASE 2 : Analyse intelligente des changements détectés
    3. 🔍 PHASE 3 : Récupération ciblée des détails par IDs (seulement les modifiés)
    
    Fonctionnalités:
    - ✅ Statuts à jour en 30s maximum (phase 1)
    - ✅ Détection précise des changements (phase 2)
    - ✅ Récupération ciblée par IDs (phase 3)
    - ✅ Performance optimisée (15-50 torrents/s)
    - ✅ Résumé post-sync avec recommandations
    
    Usage: python src/main.py --sync-smart
    Temps typique: 30s - 2 minutes
    """
    start_overall = time.time()
    logging.info("🧠 Synchronisation intelligente optimisée démarrée...")
    log_event('SYNC_START', mode='smart')
    
    # ==========================================
    # 🚀 PHASE 1 : Mise à jour rapide des statuts
    # ==========================================
    logging.info("🚀 [PHASE 1] Mise à jour ultra-rapide des statuts...")
    log_event('SYNC_PHASE_START', mode='smart', phase=1, name='status_refresh')
    
    # Sauvegarder les anciens statuts pour comparaison
    old_statuses = {}
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, status FROM torrents")
        old_statuses = dict(c.fetchall())
    
    # Utiliser torrents_only() pour mise à jour rapide des statuts
    total_torrents = asyncio.run(fetch_all_torrents(token))
    
    if total_torrents > 0:
        logging.info(f"✅ Statuts mis à jour : {total_torrents} torrents (phase 1 terminée)")
        log_event('SYNC_PHASE_END', mode='smart', phase=1, torrents=total_torrents, status='success')
    else:
        logging.info("❌ Aucun torrent récupéré, arrêt de la synchronisation")
        log_event('SYNC_ABORT', mode='smart', reason='no_torrents')
        return
    
    # ==========================================
    # 🎯 PHASE 2 : Analyse des changements
    # ==========================================
    logging.info("🎯 [PHASE 2] Analyse intelligente des changements...")
    log_event('SYNC_PHASE_START', mode='smart', phase=2, name='change_analysis')
    
    # Récupérer les nouveaux statuts après torrents_only()
    new_statuses = {}
    torrents_needing_details = set()
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Récupérer les nouveaux statuts
        c.execute("SELECT id, status FROM torrents")
        new_statuses = dict(c.fetchall())
        
        # 1. Nouveaux torrents (pas dans torrent_details)
        c.execute("""
            SELECT t.id FROM torrents t 
            LEFT JOIN torrent_details td ON t.id = td.id 
            WHERE td.id IS NULL
        """)
        new_torrents = [row[0] for row in c.fetchall()]
        
        # 2. Torrents avec changement de statut
        status_changed = []
        for torrent_id, new_status in new_statuses.items():
            old_status = old_statuses.get(torrent_id)
            if old_status != new_status:
                status_changed.append(torrent_id)
        
        # 3. Téléchargements actifs (toujours à jour)
        c.execute("""
            SELECT id FROM torrents 
            WHERE status IN ('downloading', 'queued', 'magnet_conversion')
        """)
        active_downloads = [row[0] for row in c.fetchall()]
        
        # 4. Torrents en erreur (retry)
        c.execute("""
            SELECT id FROM torrent_details 
            WHERE status = 'error'
        """)
        error_torrents = [row[0] for row in c.fetchall()]
        
        # Fusionner toutes les listes (éviter doublons)
        torrents_needing_details.update(new_torrents)
        torrents_needing_details.update(status_changed)
        torrents_needing_details.update(active_downloads)
        torrents_needing_details.update(error_torrents)
    
    # Affichage du résumé des changements détectés
    logging.info("📊 Changements détectés :")
    log_event('SYNC_ANALYSIS', new=len(new_torrents), status_changed=len(status_changed), active=len(active_downloads), errors=len(error_torrents))
    logging.info(f"   🆕 Nouveaux torrents sans détails : {len(new_torrents)}")
    logging.info(f"   🔄 Changements de statut : {len(status_changed)}")
    logging.info(f"   ⬇️  Téléchargements actifs : {len(active_downloads)}")
    logging.info(f"   ❌ Torrents en erreur (retry) : {len(error_torrents)}")
    
    torrent_ids_list = list(torrents_needing_details)
    
    if not torrent_ids_list:
        logging.info("✅ Aucun changement détecté, tous les détails sont à jour !")
        log_event('SYNC_PHASE_END', mode='smart', phase=2, status='no_changes')
        log_event('SYNC_END', mode='smart', status='success', changes=0, duration=f"{time.time()-start_overall:.2f}s")
        return
    
    total_changes = len(torrent_ids_list)
    logging.info(f"🎯 Total : {total_changes} torrents nécessitent une mise à jour des détails")
    
    # ==========================================
    # 🔍 PHASE 3 : Récupération ciblée des détails par IDs
    # ==========================================
    logging.info("🔍 [PHASE 3] Récupération ciblée des détails par IDs...")
    log_event('SYNC_PHASE_START', mode='smart', phase=3, name='details_fetch', targets=len(torrent_ids_list))
    
    # Traiter les mises à jour avec mesure du temps
    start_time = time.time()
    processed = asyncio.run(fetch_all_torrent_details_v2(token, torrent_ids_list))
    end_time = time.time()
    
    # Statistiques finales
    duration = end_time - start_time
    rate = processed / duration if duration > 0 else 0
    
    logging.info(f"✅ Synchronisation intelligente terminée !")
    logging.info(f"   📊 Phase 1 : {total_torrents} statuts mis à jour")
    logging.info(f"   📊 Phase 3 : {processed} détails mis à jour en {duration:.1f}s ({rate:.1f}/s)")
    log_event('SYNC_PHASE_END', mode='smart', phase=3, processed=processed, duration=f"{duration:.2f}s", rate=f"{rate:.2f}/s")
    
    # Étape 4: Nettoyage des torrents obsolètes
    logging.info("🧹 [PHASE 4] Nettoyage des torrents obsolètes...")
    log_event('SYNC_PHASE_START', mode='smart', phase=4, name='cleanup')
    cleaned_count = clean_obsolete_torrents(token)
    if cleaned_count > 0:
        logging.info(f"🗑️ Supprimé {cleaned_count} torrents obsolètes de la base locale")
        print(f"🧹 Nettoyage terminé: {cleaned_count} torrents obsolètes supprimés")
    else:
        logging.info("✅ Aucun torrent obsolète trouvé")
    log_event('SYNC_PHASE_END', mode='smart', phase=4, cleaned=cleaned_count, status='success')

    total_duration = time.time() - start_overall
    log_event('SYNC_END', mode='smart', status='success', torrents=total_torrents, details=processed, cleaned=cleaned_count, duration=f"{total_duration:.2f}s", rate=f"{processed/ (duration if duration>0 else 1):.2f}/s")
    
    # Afficher un résumé final
    display_final_summary()

def sync_resume(token):
    """
    Reprendre une synchronisation interrompue à partir du point d'arrêt
    
    Utilise les fichiers de progression sauvegardés pour reprendre
    exactement là où la synchronisation s'était arrêtée.
    
    Usage: python src/main.py --resume
    """
    start_time = time.time()
    logging.info("⏮️  Reprise de synchronisation...")
    log_event('SYNC_START', mode='resume')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        all_ids = [row[0] for row in c.fetchall()]
    
    processed = asyncio.run(fetch_all_torrent_details_v2(token, all_ids, resumable=True))
    logging.info(f"✅ Reprise terminée ! {processed} détails traités")
    log_event('SYNC_PART', mode='resume', details_processed=processed)
    
    # Nettoyage des torrents obsolètes
    logging.info("🧹 Nettoyage des torrents obsolètes...")
    cleaned_count = clean_obsolete_torrents(token)
    if cleaned_count > 0:
        logging.info(f"🗑️ Supprimé {cleaned_count} torrents obsolètes de la base locale")
        print(f"🧹 Nettoyage terminé: {cleaned_count} torrents obsolètes supprimés")
    else:
        logging.info("✅ Aucun torrent obsolète trouvé")
    duration = time.time() - start_time
    log_event('SYNC_END', mode='resume', status='success', details=processed, cleaned=cleaned_count, duration=f"{duration:.2f}s")

def sync_details_only(token, status_filter=None):
    """
    Synchronise uniquement les détails des torrents existants en base
    
    Args:
        token (str): Token Real-Debrid
        status_filter (str, optional): Filtre par statut (error, downloading, etc.)
        
    Usage:
        - python src/main.py --details-only
        - python src/main.py --details-only --status error
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        query = "SELECT id FROM torrents"
        params = ()
        if status_filter:
            query += " WHERE status = ?"
            params = (status_filter,)
        c.execute(query, params)
        torrent_ids = [row[0] for row in c.fetchall()]
    
    if not torrent_ids:
        logging.info("Aucun torrent trouvé pour synchronisation des détails.")
        log_event('SYNC_ABORT', mode='details_only', reason='no_torrents')
        return
        
    start_time = time.time()
    logging.info(f"🔄 Synchronisation des détails pour {len(torrent_ids)} torrents...")
    log_event('SYNC_START', mode='details_only', targets=len(torrent_ids), status_filter=status_filter or 'all')
    processed = asyncio.run(fetch_all_torrent_details(token, torrent_ids))
    logging.info(f"✅ Détails synchronisés pour {processed} torrents.")
    log_event('SYNC_PART', mode='details_only', processed=processed)
    
    # Nettoyage des torrents obsolètes
    logging.info("🧹 Nettoyage des torrents obsolètes...")
    cleaned_count = clean_obsolete_torrents(token)
    if cleaned_count > 0:
        logging.info(f"🗑️ Supprimé {cleaned_count} torrents obsolètes de la base locale")
        print(f"🧹 Nettoyage terminé: {cleaned_count} torrents obsolètes supprimés")
    else:
        logging.info("✅ Aucun torrent obsolète trouvé")
    duration = time.time() - start_time
    log_event('SYNC_END', mode='details_only', status='success', processed=processed, cleaned=cleaned_count, duration=f"{duration:.2f}s")

def sync_torrents_only(token):
    """
    Synchronisation ultra-rapide des torrents de base uniquement (sans détails)
    
    Parfait pour:
    - Vue d'ensemble rapide de la collection
    - Première découverte avant sync complet
    - Monitoring des nouveaux ajouts
    
    Usage: python src/main.py --torrents-only
    Temps typique: 10-30 secondes
    """
    start_time = time.time()
    logging.info("📋 Synchronisation des torrents de base uniquement...")
    log_event('SYNC_START', mode='torrents_only')
    
    total = asyncio.run(fetch_all_torrents(token))
    
    if total > 0:
        logging.info(f"✅ Synchronisation terminée ! {total} torrents enregistrés dans la table 'torrents'")
        log_event('SYNC_PART', mode='torrents_only', torrents=total)
        
        # Nettoyage des torrents obsolètes
        logging.info("🧹 Nettoyage des torrents obsolètes...")
        cleaned_count = clean_obsolete_torrents(token)
        if cleaned_count > 0:
            logging.info(f"🗑️ Supprimé {cleaned_count} torrents obsolètes de la base locale")
            print(f"🧹 Nettoyage terminé: {cleaned_count} torrents obsolètes supprimés")
        else:
            logging.info("✅ Aucun torrent obsolète trouvé")
        duration = time.time() - start_time
        log_event('SYNC_END', mode='torrents_only', status='success', torrents=total, cleaned=cleaned_count, duration=f"{duration:.2f}s")
        
        # Afficher un petit résumé
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT status, COUNT(*) FROM torrents GROUP BY status")
            status_counts = dict(c.fetchall())
            
            print(f"\n📊 Résumé des torrents synchronisés:")
            for status, count in status_counts.items():
                emoji = get_status_emoji(status)
                print(f"   {emoji} {status}: {count}")
    else:
        logging.info("ℹ️  Aucun torrent trouvé ou synchronisé")
        log_event('SYNC_ABORT', mode='torrents_only', reason='no_torrents')

def clean_obsolete_torrents(token):
    """
    Nettoie les torrents qui existent localement mais qui ne sont plus présents côté Real-Debrid
    
    Cette fonction récupère la liste actuelle des torrents depuis Real-Debrid et supprime
    de la base locale tous les torrents qui n'y figurent plus.
    
    Args:
        token (str): Token d'authentification Real-Debrid
        
    Returns:
        int: Nombre de torrents supprimés
    """
    logging.info("🔍 Récupération de la liste actuelle des torrents Real-Debrid...")
    
    # Récupérer tous les IDs de torrents actuels côté Real-Debrid
    current_rd_ids = set()
    headers = {"Authorization": f"Bearer {token}"}
    limit = 5000
    
    try:
        import aiohttp
        import asyncio
        
        async def get_current_torrent_ids():
            page = 1
            async with aiohttp.ClientSession() as session:
                while True:
                    params = {"page": page, "limit": limit}
                    try:
                        torrents = await api_request(session, RD_API_URL, headers, params)
                        if not torrents:
                            break
                        
                        for t in torrents:
                            current_rd_ids.add(t['id'])
                        
                        if len(torrents) < limit:
                            break
                            
                        page += 1
                        await asyncio.sleep(1)  # Pause entre pages
                        
                    except Exception as e:
                        logging.error(f"Erreur lors de la récupération des IDs Real-Debrid: {e}")
                        break
        
        # Exécuter la récupération
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(get_current_torrent_ids())
        loop.close()
        
        if not current_rd_ids:
            logging.warning("⚠️ Aucun torrent trouvé côté Real-Debrid, nettoyage annulé par sécurité")
            return 0
        
        logging.info(f"✅ {len(current_rd_ids)} torrents trouvés côté Real-Debrid")
        
        # Récupérer tous les IDs locaux
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM torrents")
            local_ids = {row[0] for row in c.fetchall()}
        
        # Identifier les torrents obsolètes (présents localement mais pas côté Real-Debrid)
        obsolete_ids = local_ids - current_rd_ids
        
        if not obsolete_ids:
            logging.info("✅ Aucun torrent obsolète trouvé")
            return 0
        
        logging.info(f"🗑️ {len(obsolete_ids)} torrents obsolètes détectés")
        
        # Supprimer les torrents obsolètes des deux tables
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Supprimer de torrents
            placeholders = ','.join('?' * len(obsolete_ids))
            c.execute(f"DELETE FROM torrents WHERE id IN ({placeholders})", list(obsolete_ids))
            torrents_deleted = c.rowcount
            
            # Supprimer de torrent_details
            c.execute(f"DELETE FROM torrent_details WHERE id IN ({placeholders})", list(obsolete_ids))
            details_deleted = c.rowcount
            
            conn.commit()
        
        logging.info(f"🗑️ Supprimé {torrents_deleted} entrées de 'torrents' et {details_deleted} entrées de 'torrent_details'")
        return len(obsolete_ids)
        
    except Exception as e:
        logging.error(f"❌ Erreur lors du nettoyage des torrents obsolètes: {e}")
        return 0

def sync_all_v2(token):
    """
    Synchronisation complète optimisée (SYNC RAPIDE)
    
    Effectue une synchronisation complète des torrents et détails avec optimisations:
    - Récupération de tous les torrents de base
    - Récupération de tous les détails manquants
    - Optimisé pour première utilisation ou sync complet
    
    Usage: python src/main.py --sync-fast
    Temps typique: 7-10 minutes
    """
    start_time = time.time()
    logging.info("🚀 Synchronisation complète optimisée en cours...")
    log_event('SYNC_START', mode='fast')
    
    # Étape 1: Synchroniser tous les torrents de base
    logging.info("📥 Étape 1/2: Récupération des torrents de base...")
    total_torrents = asyncio.run(fetch_all_torrents(token))
    
    if total_torrents == 0:
        logging.warning("⚠️ Aucun torrent trouvé")
        print("⚠️ Aucun torrent trouvé dans votre compte Real-Debrid")
        log_event('SYNC_ABORT', mode='fast', reason='no_torrents')
        return
    
    logging.info(f"✅ {total_torrents} torrents de base récupérés")
    
    # Étape 2: Récupérer tous les détails manquants
    logging.info("📋 Étape 2/2: Récupération des détails...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents WHERE id NOT IN (SELECT id FROM torrent_details)")
        missing_ids = [row[0] for row in c.fetchall()]
    
    if missing_ids:
        logging.info(f"🔄 Récupération des détails pour {len(missing_ids)} torrents...")
        log_event('SYNC_PART', mode='fast', missing_details=len(missing_ids))
        processed = asyncio.run(fetch_all_torrent_details_v2(token, missing_ids))
        logging.info(f"✅ Détails récupérés pour {processed} torrents")
        print(f"🚀 Synchronisation complète terminée: {total_torrents} torrents, {processed} détails")
        log_event('SYNC_PART', mode='fast', details_processed=processed)
    else:
        logging.info("✅ Tous les détails sont déjà à jour")
        print(f"🚀 Synchronisation complète terminée: {total_torrents} torrents, tous les détails à jour")
        log_event('SYNC_PART', mode='fast', missing_details=0)
    
    # Étape 3: Nettoyage des torrents obsolètes
    logging.info("🧹 Étape 3/3: Nettoyage des torrents obsolètes...")
    cleaned_count = clean_obsolete_torrents(token)
    if cleaned_count > 0:
        logging.info(f"🗑️ Supprimé {cleaned_count} torrents obsolètes de la base locale")
        print(f"🧹 Nettoyage terminé: {cleaned_count} torrents obsolètes supprimés")
    else:
        logging.info("✅ Aucun torrent obsolète trouvé")
    duration = time.time() - start_time
    log_event('SYNC_END', mode='fast', status='success', torrents=total_torrents, cleaned=cleaned_count, duration=f"{duration:.2f}s")
    
    display_final_summary()

async def fetch_all_torrent_details(token, torrent_ids, max_concurrent=MAX_CONCURRENT):
    """
    Version classique de récupération des détails (pour compatibilité)
    
    Args:
        token (str): Token Real-Debrid
        torrent_ids (list): IDs des torrents à traiter
        max_concurrent (int): Nombre de requêtes simultanées
        
    Returns:
        int: Nombre de détails traités
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    total_processed = 0
    
    async with aiohttp.ClientSession() as session:
        async def process_torrent(tid):
            async with semaphore:
                return await fetch_torrent_detail(session, token, tid)
        
        # Traitement par batch pour respecter les quotas
        for i in range(0, len(torrent_ids), BATCH_SIZE):
            if stop_requested:
                logging.info("Arrêt demandé, interruption de la récupération des détails.")
                break
                
            batch_ids = torrent_ids[i:i+BATCH_SIZE]
            tasks = [process_torrent(tid) for tid in batch_ids]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Compter les succès
            successful = sum(1 for r in batch_results if r and not isinstance(r, Exception))
            total_processed += successful
            
            logging.info(f"Batch {i//BATCH_SIZE + 1}: {successful}/{len(batch_ids)} détails récupérés")
            
            # Pause entre les batches sauf pour le dernier
            if i + BATCH_SIZE < len(torrent_ids):
                logging.info(f"Pause {QUOTA_WAIT_TIME}s avant le prochain batch...")
                await asyncio.sleep(QUOTA_WAIT_TIME)
    
    return total_processed

def display_final_summary():
    """
    Affiche un résumé final après synchronisation avec recommandations
    
    Informations affichées:
    - Statistiques générales
    - Répartition par statut
    - Activité récente
    - Recommandations d'actions
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Statistiques générales
            c.execute("SELECT COUNT(*) FROM torrents")
            total_torrents = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM torrent_details")
            total_details = c.fetchone()[0]
            
            # Répartition par statut (top 5) - CORRIGER: utiliser seulement torrent_details
            c.execute("""
                SELECT td.status, COUNT(*) as count
                FROM torrent_details td
                WHERE td.status IS NOT NULL
                GROUP BY td.status
                ORDER BY count DESC
                LIMIT 5
            """)
            status_counts = c.fetchall()
            
            # Torrents récents (dernières 24h)
            c.execute("""
                SELECT COUNT(*) FROM torrents 
                WHERE datetime('now') - datetime(added_on) < 1
            """)
            recent_count = c.fetchone()[0]
            
            print(f"\n📊 Résumé de la base de données :")
            print(f"   📂 Total torrents : {total_torrents}")
            print(f"   📝 Avec détails : {total_details} ({100*total_details/total_torrents:.1f}%)")
            print(f"   🆕 Ajoutés récemment (24h) : {recent_count}")
            
            if status_counts:
                print(f"\n📈 Top 5 des statuts :")
                for status, count in status_counts:
                    percentage = 100 * count / total_torrents if total_torrents > 0 else 0
                    emoji = get_status_emoji(status)
                    print(f"   {emoji} {status} : {count} ({percentage:.1f}%)")
                    
    except Exception as e:
        logging.warning(f"Impossible d'afficher le résumé : {e}")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                      SECTION 6: STATISTIQUES ET ANALYTICS                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def show_stats():
    """
    Affiche des statistiques complètes et détaillées de votre collection
    
    Sections d'analyse:
    - 🗂️ Vue d'ensemble générale
    - 💾 Volumes de données  
    - ⏰ Activité récente
    - 🔄 État des téléchargements
    - 📈 Répartition par statut
    - 🌐 Top hébergeurs
    - 🏆 Plus gros torrents
    - 💡 Recommandations automatiques
    
    Usage: python src/main.py --stats
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # === STATISTIQUES GÉNÉRALES ===
        c.execute("SELECT COUNT(*) FROM torrents")
        total_torrents = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM torrent_details")
        total_details = c.fetchone()[0]
        
        coverage_percent = (total_details / total_torrents * 100) if total_torrents > 0 else 0
        
        # === RÉPARTITION PAR STATUT ===
        c.execute("SELECT status, COUNT(*) FROM torrent_details WHERE status IS NOT NULL GROUP BY status ORDER BY COUNT(*) DESC")
        torrent_status = c.fetchall()
        
        c.execute("SELECT status, COUNT(*) FROM torrent_details GROUP BY status ORDER BY COUNT(*) DESC")
        detail_status = c.fetchall()
        
        # === TAILLES ET VOLUMES ===
        c.execute("SELECT SUM(bytes), MIN(bytes), MAX(bytes) FROM torrents WHERE bytes > 0")
        size_stats = c.fetchone()
        total_size, min_size, max_size = size_stats if size_stats and size_stats[0] else (0, 0, 0)
        
        # === ACTIVITÉ RÉCENTE ===
        c.execute("""
            SELECT COUNT(*) FROM torrents 
            WHERE datetime(added_on) >= datetime('now', '-24 hours')
        """)
        recent_24h = c.fetchone()[0] or 0
        
        c.execute("""
            SELECT COUNT(*) FROM torrents 
            WHERE datetime(added_on) >= datetime('now', '-7 days')
        """)
        recent_7d = c.fetchone()[0] or 0
        
        # === TORRENTS PROBLÉMATIQUES ===
        c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'error' OR error IS NOT NULL")
        error_count = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM torrent_details WHERE status IN ('downloading', 'queued', 'waiting_files_selection')")
        active_count = c.fetchone()[0] or 0
        
        # === TORRENTS SANS DÉTAILS ===
        c.execute("""
            SELECT COUNT(*) FROM torrents t 
            LEFT JOIN torrent_details td ON t.id = td.id 
            WHERE td.id IS NULL
        """)
        missing_details = c.fetchone()[0] or 0
        
        # === TOP HÉBERGEURS ===
        c.execute("""
            SELECT host, COUNT(*) as count 
            FROM torrent_details 
            WHERE host IS NOT NULL AND host != ''
            GROUP BY host 
            ORDER BY count DESC 
            LIMIT 5
        """)
        top_hosts = c.fetchall()
        
        # === TORRENTS LES PLUS GROS ===
        c.execute("""
            SELECT name, size, status 
            FROM torrent_details 
            WHERE size > 0 AND name IS NOT NULL
            ORDER BY size DESC 
            LIMIT 5
        """)
        biggest_torrents = c.fetchall()
        
        # === PROGRESSION MOYENNE ===
        c.execute("SELECT AVG(progress) FROM torrent_details WHERE progress IS NOT NULL")
        avg_progress = c.fetchone()[0] or 0
        
        # === AFFICHAGE FORMATÉ ===
        print("\n" + "="*60)
        print("📊 STATISTIQUES COMPLÈTES REDRIVA")
        print("="*60)
        
        # Vue d'ensemble
        print(f"\n🗂️  VUE D'ENSEMBLE")
        print(f"   📁 Total torrents     : {total_torrents:,}")
        print(f"   📋 Détails disponibles: {total_details:,}")
        print(f"   📊 Couverture         : {coverage_percent:.1f}%")
        print(f"   ❌ Détails manquants  : {missing_details:,}")
        
        # Volumes de données
        if total_size and total_size > 0:
            print(f"\n💾 VOLUMES DE DONNÉES")
            print(f"   📦 Volume total       : {format_size(total_size)}")
            print(f"    Plus petit         : {format_size(min_size) if min_size else 'N/A'}")
            print(f"   🔺 Plus gros          : {format_size(max_size) if max_size else 'N/A'}")
        
        # Activité récente
        print(f"\n⏰ ACTIVITÉ RÉCENTE")
        print(f"   🆕 Dernières 24h      : {recent_24h:,} torrents")
        print(f"   📅 Derniers 7 jours   : {recent_7d:,} torrents")
        
        # État des téléchargements
        print(f"\n🔄 ÉTAT DES TÉLÉCHARGEMENTS")
        print(f"   ✅ Progression moyenne: {avg_progress:.1f}%")
        print(f"   ⬇️  Téléchargements    : {active_count:,}")
        print(f"   ❌ Erreurs            : {error_count:,}")
        
        # Répartition par statut (torrents)
        if torrent_status:
            print(f"\n📈 RÉPARTITION PAR STATUT")
            for status, count in torrent_status[:8]:  # Top 8
                percent = (count / total_torrents * 100) if total_torrents > 0 else 0
                status_emoji = get_status_emoji(status)
                print(f"   {status_emoji} {status:<15} : {count:,} ({percent:.1f}%)")
        
        # Top hébergeurs
        if top_hosts:
            print(f"\n🌐 TOP HÉBERGEURS")
            for host, count in top_hosts:
                percent = (count / total_details * 100) if total_details > 0 else 0
                print(f"   🔗 {host:<15} : {count:,} ({percent:.1f}%)")
        
        # Plus gros torrents
        if biggest_torrents:
            print(f"\n🏆 TOP 5 PLUS GROS TORRENTS")
            for i, (name, size, status) in enumerate(biggest_torrents, 1):
                status_emoji = get_status_emoji(status)
                truncated_name = (name[:45] + "...") if len(name) > 48 else name
                print(f"   {i}. {status_emoji} {format_size(size)} - {truncated_name}")
        
        # Recommandations automatiques
        print(f"\n💡 RECOMMANDATIONS")
        if missing_details > 0:
            print(f"   🔧 Exécuter: python src/main.py --sync-smart")
            print(f"      (pour récupérer {missing_details:,} détails manquants)")
        
        if error_count > 0:
            print(f"   🔄 Exécuter: python src/main.py --details-only --status error")
            print(f"      (pour retry {error_count:,} torrents en erreur)")
        
        if active_count > 0:
            print(f"   ⬇️  {active_count:,} téléchargements en cours")
            print(f"      (utilisez --sync-smart pour les suivre)")
        
        if missing_details == 0 and error_count == 0:
            print(f"   ✅ Votre base est complète et à jour !")
        
        print("\n" + "="*60)

def show_stats_compact():
    """
    Version compacte des statistiques sur une ligne pour usage fréquent
    
    Parfait pour:
    - Monitoring quotidien rapide
    - Scripts automatisés
    - Check rapide avant sync
    
    Usage: python src/main.py --stats --compact
    Exemple: 📊 4,233 torrents | 4,232 détails (100.0%) | ⬇️ 0 en cours | ❌ 2 erreurs
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM torrents")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM torrent_details")
        details = c.fetchone()[0]
        
        # Utilisation des constantes pour les torrents actifs
        placeholders = ','.join('?' * len(ACTIVE_STATUSES))
        c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ACTIVE_STATUSES)
        active = c.fetchone()[0] or 0
        
        # Utilisation des constantes pour les erreurs
        placeholders = ','.join('?' * len(ERROR_STATUSES))
        c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ERROR_STATUSES)
        errors = c.fetchone()[0] or 0
        
        coverage = (details / total * 100) if total > 0 else 0
        
        print(f"📊 {total:,} torrents | {details:,} détails ({coverage:.1f}%) | "
              f"⬇️ {active} actifs | ❌ {errors} erreurs")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                     SECTION 7: DIAGNOSTIC ET MAINTENANCE                  ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def analyze_error_type(error_msg, status):
    """
    Analyse automatique du type d'erreur basé sur le message d'erreur
    
    Types d'erreurs détectés:
    - ⏱️ Timeout réseau (temporaire)
    - 🔍 Torrent introuvable (supprimé de RD)
    - 🚫 Accès refusé (problème d'autorisation)
    - 🖥️ Erreur serveur Real-Debrid
    - 📊 Quota API dépassé
    - 🌐 Problème de connexion
    - 📋 Données malformées
    
    Args:
        error_msg (str): Message d'erreur
        status (str): Statut du torrent
        
    Returns:
        str: Type d'erreur avec emoji et description
    """
    if not error_msg:
        return "❓ Erreur inconnue (pas de message)"
    
    error_lower = error_msg.lower()
    
    if "timeout" in error_lower or "time out" in error_lower:
        return "⏱️ Timeout réseau (temporaire)"
    elif "404" in error_lower or "not found" in error_lower:
        return "🔍 Torrent introuvable (supprimé de RD)"
    elif "403" in error_lower or "forbidden" in error_lower:
        return "🚫 Accès refusé (problème d'autorisation)"
    elif "500" in error_lower or "502" in error_lower or "503" in error_lower:
        return "🖥️ Erreur serveur Real-Debrid (temporaire)"
    elif "quota" in error_lower or "limit" in error_lower:
        return "📊 Quota API dépassé (temporaire)"
    elif "connection" in error_lower:
        return "🌐 Problème de connexion (temporaire)"
    elif "json" in error_lower or "parse" in error_lower:
        return "📋 Données malformées (temporaire)"
    else:
        return f"❓ Erreur spécifique : {error_msg[:50]}..."

def get_error_suggestion(error_msg, status):
    """
    Propose une solution spécifique basée sur le type d'erreur détecté
    
    Args:
        error_msg (str): Message d'erreur
        status (str): Statut du torrent
        
    Returns:
        str: Suggestion d'action corrective avec emoji
    """
    if not error_msg:
        return "🔄 Retry avec --sync-smart"
    
    error_lower = error_msg.lower()
    
    if "timeout" in error_lower or "connection" in error_lower:
        return "🔄 Retry automatique recommandé (erreur réseau temporaire)"
    elif "404" in error_lower or "not found" in error_lower:
        return "🗑️ Torrent probablement supprimé - considérer suppression de la base"
    elif "403" in error_lower:
        return "🔑 Vérifier la validité du token Real-Debrid"
    elif "500" in error_lower or "502" in error_lower:
        return "⏳ Attendre et retry plus tard (problème serveur RD)"
    elif "quota" in error_lower:
        return "⏰ Attendre la réinitialisation du quota (1 heure max)"
    else:
        return "🔄 Retry avec --sync-smart ou --details-only --status error"

def diagnose_errors():
    """
    Diagnostique détaillé des torrents en erreur avec analyse automatique
    
    Fonctionnalités:
    - 📋 Informations complètes de chaque erreur
    - 🔬 Analyse automatique du type d'erreur
    - 💡 Suggestions d'actions correctives
    - 📊 Résumé statistique par type d'erreur
    - 🛠️ Commandes exactes pour résoudre
    
    Usage: python src/main.py --diagnose-errors
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Récupérer tous les torrents en erreur avec leurs détails
        c.execute("""
            SELECT td.id, td.name, td.status, td.error, td.progress, 
                   t.filename, t.added_on, t.bytes
            FROM torrent_details td
            LEFT JOIN torrents t ON td.id = t.id
            WHERE td.status = 'error' OR td.error IS NOT NULL
            ORDER BY t.added_on DESC
        """)
        
        errors = c.fetchall()
        
        if not errors:
            print("✅ Aucun torrent en erreur trouvé !")
            return
        
        print(f"\n🔍 DIAGNOSTIC DES ERREURS ({len(errors)} torrents)")
        print("="*80)
        
        # Analyse détaillée de chaque erreur
        for i, (torrent_id, name, status, error, progress, filename, added_on, bytes_size) in enumerate(errors, 1):
            print(f"\n❌ ERREUR #{i}")
            print(f"   🆔 ID             : {torrent_id}")
            print(f"   📁 Nom            : {name or filename or 'N/A'}")
            print(f"   📊 Statut         : {status}")
            print(f"   ⚠️  Message d'erreur: {error or 'Aucun message spécifique'}")
            print(f"   📈 Progression    : {progress or 0}%")
            print(f"   📅 Ajouté le      : {added_on}")
            print(f"   💾 Taille         : {format_size(bytes_size) if bytes_size else 'N/A'}")
            
            # Analyse automatique du type d'erreur
            error_type = analyze_error_type(error, status)
            print(f"   🔬 Type d'erreur  : {error_type}")
            
            # Suggestion de correction personnalisée
            suggestion = get_error_suggestion(error, status)
            print(f"   💡 Suggestion     : {suggestion}")
            print("-" * 80)
        
        # Résumé statistique des types d'erreurs
        print(f"\n📊 RÉSUMÉ DES TYPES D'ERREURS")
        error_types = {}
        for _, _, _, error, _, _, _, _ in errors:
            error_type = analyze_error_type(error, None)
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {error_type} : {count}")
        
        # Actions recommandées avec commandes exactes
        print(f"\n💡 ACTIONS RECOMMANDÉES :")
        print(f"   🔄 Retry automatique    : python src/main.py --sync-smart")
        print(f"   🎯 Retry forcé          : python src/main.py --details-only --status error")
        print(f"   📊 Vérifier l'état      : python src/main.py --stats")



# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    SECTION 8: INTERFACE UTILISATEUR (MENU)                ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def show_interactive_menu():
    """
    Menu interactif principal pour faciliter l'utilisation de Redriva
    
    Fonctionnalités:
    - 🎯 Interface guidée avec choix numérotés
    - ⚡ Accès direct aux fonctions principales
    - 💡 Guide intégré avec recommandations
    - 🔄 Navigation fluide avec retour automatique
    - 🏃 Mode hybride vers ligne de commande
    
    Categories du menu:
    - 📊 Informations & Diagnostic  
    - 🔄 Synchronisation
    - 🔧 Maintenance
    - ❓ Aide & Sortie
    
    Returns:
        bool: True si le programme doit se terminer, False pour continuer en CLI
    """
    import os
    
    while True:
        # Effacer l'écran (compatible Linux/Mac/Windows)
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 20 + "🚀 MENU REDRIVA" + " " * 20 + "║")
        print("╠" + "═" * 58 + "╣")
        print("║ Outil de synchronisation Real-Debrid                  ║")
        print("╚" + "═" * 58 + "╝")
        
        print("\n📊 INFORMATIONS & DIAGNOSTIC")
        print("  1. 📈 Statistiques complètes")
        print("  2. 📋 Statistiques compactes")
        print("  3. 🔍 Diagnostiquer les erreurs")
        
        print("\n🔄 SYNCHRONISATION")
        print("  4. 🧠 Sync intelligent (recommandé)")
        print("  5. 🚀 Sync complet")
        print("  6. 📋 Vue d'ensemble (ultra-rapide)")
        print("  7. ⏮️  Reprendre sync interrompu")
        
        print("\n🔧 MAINTENANCE")
        print("  8. 🔄 Détails uniquement")
        print("  9. 🗑️  Vider la base de données")
        print(" 10. 🔍 Diagnostic du token")
        
        print("\n❓ AIDE & SORTIE")
        print(" 11. 💡 Guide de choix rapide")
        print(" 12. 🏃 Mode commande (passer aux arguments)")
        print("  0. 🚪 Quitter")
        
        print("\n" + "─" * 60)
        
        try:
            choice = input("👉 Votre choix (0-12) : ").strip()
            
            if choice == "0":
                print("\n👋 Au revoir ! Merci d'utiliser Redriva.")
                break
                
            elif choice == "1":
                print("\n🔄 Chargement des statistiques complètes...")
                show_stats()
                input("\n📊 Appuyez sur Entrée pour continuer...")
                
            elif choice == "2":
                print("\n📊 Statistiques compactes :")
                show_stats_compact()
                input("\n📋 Appuyez sur Entrée pour continuer...")
                
            elif choice == "3":
                print("\n🔍 Diagnostic des erreurs en cours...")
                diagnose_errors()
                input("\n🔧 Appuyez sur Entrée pour continuer...")
                
            elif choice == "4":
                token = get_token()
                if token:
                    print("\n🧠 Synchronisation intelligente en cours...")
                    sync_smart(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "5":
                token = get_token()
                if token:
                    print("\n🚀 Synchronisation rapide en cours...")
                    sync_all_v2(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "6":
                token = get_token()
                if token:
                    print("\n📋 Synchronisation des torrents uniquement...")
                    sync_torrents_only(token)
                    input("\n📋 Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "7":
                token = get_token()
                if token:
                    print("\n⏮️  Reprise de la synchronisation...")
                    sync_resume(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "8":
                token = get_token()
                if token:
                    print("\n🔄 Mise à jour des détails uniquement...")
                    sync_details_only(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "9":
                confirm = input("\n⚠️  ATTENTION : Vider complètement la base de données ? (tapez 'SUPPRIMER'): ")
                if confirm == "SUPPRIMER":
                    clear_database()
                    input("\n🗑️  Base vidée. Appuyez sur Entrée pour continuer...")
                else:
                    print("❌ Annulé.")
                    input("📋 Appuyez sur Entrée pour continuer...")
                    
            elif choice == "10":
                print("\n❌ Option non disponible")
                input("� Appuyez sur Entrée pour continuer...")
                
            elif choice == "11":
                print("\n❌ Option non disponible")
                input("� Appuyez sur Entrée pour continuer...")
                
            elif choice == "12":
                print("\n🏃 Passage en mode commande...")
                print("💡 Utilisez: python src/main.py --help pour voir toutes les options")
                print("📋 Exemple: python src/main.py --sync-smart")
                return False  # Retourne False pour continuer avec les arguments CLI
                
            else:
                input("\n❌ Choix invalide. Appuyez sur Entrée pour continuer...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Interruption détectée. Au revoir !")
            break
        except Exception as e:
            print(f"\n❌ Erreur : {e}")
            input("🔧 Appuyez sur Entrée pour continuer...")
    
    return True  # Retourne True si le programme doit se terminer



def get_token():
    """
    Récupère le token Real-Debrid depuis la configuration centralisée
    Returns:
        str/None: Token valide ou None si non trouvé
    """
    try:
        return load_token()
    except SystemExit:
        print("\n❌ ERREUR : Token Real-Debrid non trouvé !")
        print("🔧 Veuillez configurer votre token via l'interface web de Redriva.")
        return None

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                        SECTION 9: POINT D'ENTRÉE PRINCIPAL                ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def main():
    """
    Point d'entrée principal avec support menu interactif et arguments CLI
    
    Logique:
    - Si aucun argument : lance le menu interactif
    - Sinon : traite les arguments de ligne de commande
    
    Arguments supportés:
    - Synchronisation : --sync-all, --sync-fast, --sync-smart, --resume, etc.
    - Statistiques : --stats, --stats --compact  
    - Diagnostic : --diagnose-errors
    - Maintenance : --details-only, --clear, --torrents-only
    """
    
    parser = argparse.ArgumentParser(description="Redriva - Synchroniseur Real-Debrid vers SQLite")
    
    # Si aucun argument n'est fourni, lancer le menu interactif
    if len(sys.argv) == 1:
        try:
            should_exit = show_interactive_menu()
            if should_exit:
                return
        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            return
    
    # === ARGUMENTS DE LIGNE DE COMMANDE ===
    
    # Arguments de base
    parser.add_argument('--details-only', action='store_true', 
                       help="📝 Synchroniser uniquement les détails des torrents existants")
    parser.add_argument('--status', 
                       help="🔍 Filtrer par status (downloaded, error, downloading, etc.)")
    parser.add_argument('--stats', action='store_true', 
                       help="📊 Afficher les statistiques de la base")
    parser.add_argument('--compact', action='store_true', 
                       help="📋 Affichage compact des statistiques")
    parser.add_argument('--clear', action='store_true', 
                       help="🗑️ Vider complètement la base de données")
    
    # Arguments de synchronisation (architecture simplifiée)
    parser.add_argument('--sync-smart', action='store_true', 
                       help="🧠 Sync intelligent - Mode recommandé (30s-2min)")
    parser.add_argument('--sync-fast', action='store_true', 
                       help="🚀 Sync complet - Synchronisation complète optimisée (7-10min)")
    parser.add_argument('--torrents-only', action='store_true', 
                       help="📋 Vue d'ensemble - Liste des torrents uniquement (10-30s)")
    parser.add_argument('--resume', action='store_true', 
                       help="⏮️  Reprendre une synchronisation interrompue")
    
    # Arguments de diagnostic
    parser.add_argument('--diagnose-errors', action='store_true', 
                       help="🔍 Diagnostic détaillé des torrents en erreur avec suggestions")
    parser.add_argument('--menu', action='store_true', 
                       help="🎮 Afficher le menu interactif")
    
    args = parser.parse_args()

    # Initialisation
    token = load_token()
    create_tables()

    try:
        # === TRAITEMENT DES ARGUMENTS ===
        
        if args.menu:
            show_interactive_menu()
            
        elif args.clear:
            # Demander confirmation avant de vider
            response = input("⚠️  Êtes-vous sûr de vouloir vider la base de données ? (oui/non): ")
            if response.lower() in ['oui', 'o', 'yes', 'y']:
                clear_database()
            else:
                print("❌ Opération annulée.")
                
        elif args.stats:
            if args.compact:
                show_stats_compact()
            else:
                show_stats()
                
        elif args.diagnose_errors:
            diagnose_errors()
            
        elif args.torrents_only:
            sync_torrents_only(token)
            
        elif args.sync_fast:
            sync_all_v2(token)
            
        elif args.sync_smart:
            sync_smart(token)
            
        elif args.resume:
            sync_resume(token)
            
        elif args.details_only:
            sync_details_only(token, args.status)
            
        else:
            # Aucun argument reconnu, afficher l'aide
            parser.print_help()
            print(f"\n💡 Astuce : Lancez simplement 'python src/main.py' pour le menu interactif !")
            
    except KeyboardInterrupt:
        logging.warning("Arrêt manuel par l'utilisateur.")
    except Exception as e:
        logging.error(f"Erreur inattendue : {e}")

if __name__ == "__main__":
    main()
