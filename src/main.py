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
from pathlib import Path

def load_env_file():
    """
    Charge les variables d'environnement depuis le fichier .env
    
    Permet une configuration flexible sans modifier le code.
    Variables supportées: RD_TOKEN, RD_MAX_CONCURRENT, RD_BATCH_SIZE, etc.
    """
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Ne pas écraser les variables déjà définies
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip()

# Chargement des variables d'environnement depuis .env
load_env_file()

# Configuration du logging avec format enrichi
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Gestion de l'interruption propre (CTRL+C)
stop_requested = False
def handle_sigint(signum, frame):
    """Gestionnaire d'interruption propre pour éviter la corruption de données"""
    global stop_requested
    logging.warning("Interruption clavier reçue (CTRL+C), arrêt propre...")
    stop_requested = True

signal.signal(signal.SIGINT, handle_sigint)

# Configuration via variables d'environnement avec valeurs par défaut optimisées
RD_API_URL = "https://api.real-debrid.com/rest/1.0/torrents"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/redriva.db'))
MAX_CONCURRENT = int(os.getenv('RD_MAX_CONCURRENT', '50'))    # Requêtes simultanées
BATCH_SIZE = int(os.getenv('RD_BATCH_SIZE', '250'))          # Taille des batches
QUOTA_WAIT_TIME = int(os.getenv('RD_QUOTA_WAIT', '60'))      # Attente quota global (sec)
TORRENT_QUOTA_WAIT = int(os.getenv('RD_TORRENT_WAIT', '10')) # Attente quota torrent (sec)

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
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
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
            hash TEXT,
            host TEXT,
            error TEXT,
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
    
    cursor.execute("DELETE FROM sync_progress")
    cursor.execute("DELETE FROM torrent_details")
    cursor.execute("DELETE FROM torrents")
    
    # Reset des auto-increment
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('torrents', 'torrent_details', 'sync_progress')")
    
    conn.commit()
    conn.close()
    
    logging.info("Base de données vidée avec succès")
    print("✅ Base de données complètement vidée")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                           SECTION 4: API REAL-DEBRID                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def load_token():
    """
    Récupère le token Real-Debrid avec nettoyage et validation maximum
    Gère tous les cas d'erreurs possibles pour éviter Header Injection
    
    Priorité de recherche:
    1. Variable d'environnement RD_TOKEN
    2. Fichier config/rd_token.conf
    3. Fichier .env (fallback)
    
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
        if len(token) < 20 or len(token) > 100:
            return None
            
        return token
    
    def extract_token_from_file(filepath):
        """Extrait le token d'un fichier en ignorant commentaires et lignes vides"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Ignorer les lignes vides et les commentaires
                    if line and not line.startswith('#'):
                        # Prendre la première ligne valide trouvée
                        cleaned = clean_token(line)
                        if cleaned:
                            return cleaned
            return None
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            return None
    
    # Chargement des variables d'environnement
    load_env_file()
    
    # Tentative 1 : Variable d'environnement RD_TOKEN
    env_token = os.environ.get("RD_TOKEN")
    if env_token:
        cleaned_env = clean_token(env_token)
        if cleaned_env:
            logging.debug("✅ Token récupéré depuis variable d'environnement")
            return cleaned_env
        else:
            logging.warning("⚠️  Variable RD_TOKEN contient un token invalide")
    
    # Tentative 2 : Fichier config/rd_token.conf
    config_path = os.path.join(os.path.dirname(__file__), "../config/rd_token.conf")
    config_token = extract_token_from_file(config_path)
    if config_token:
        logging.debug("✅ Token récupéré depuis config/rd_token.conf")
        return config_token
    
    # Tentative 3 : Fichier .env (secours)
    env_file_token = None
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.strip().startswith('RD_TOKEN='):
                    env_file_token = line.split('=', 1)[1]
                    break
        
        if env_file_token:
            cleaned_env_file = clean_token(env_file_token)
            if cleaned_env_file:
                logging.debug("✅ Token récupéré depuis fichier .env")
                return cleaned_env_file
    except FileNotFoundError:
        pass
    
    # Aucun token valide trouvé
    logging.error("❌ Aucun token Real-Debrid valide trouvé")
    logging.error("💡 Veuillez configurer votre token :")
    logging.error("   • Variable : export RD_TOKEN='votre_token'")
    logging.error("   • Fichier  : echo -n 'votre_token' > config/rd_token.conf")
    
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
    Récupère tous les torrents depuis l'API Real-Debrid
    
    Utilise la pagination pour récupérer tous les torrents par batches de 1000.
    Sauvegarde directement en base pour éviter la surcharge mémoire.
    
    Args:
        token (str): Token d'authentification Real-Debrid
        
    Returns:
        int: Nombre total de torrents récupérés
    """
    headers = {"Authorization": f"Bearer {token}"}
    limit = 1000
    page = 1
    total = 0
    
    async with aiohttp.ClientSession() as session:
        while True:
            if stop_requested:
                logging.info("Arrêt demandé, interruption de la récupération des torrents.")
                break
                
            params = {"page": page, "limit": limit}
            torrents = await api_request(session, RD_API_URL, headers, params)
            
            if not torrents:
                break
                
            # Sauvegarde immédiate en base
            for t in torrents:
                upsert_torrent(t)
                
            total += len(torrents)
            logging.info(f"Page {page}: {len(torrents)} torrents (total: {total})")
            page += 1
            
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
        
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO torrent_details
            (id, name, status, size, files_count, progress, links, hash, host, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                detail.get('id'),
                detail.get('filename') or detail.get('name'),
                detail.get('status'),
                detail.get('bytes'),
                len(detail.get('files', [])),
                detail.get('progress'),
                ",".join(detail.get('links', [])) if detail.get('links') else None,
                detail.get('hash'),
                detail.get('host'),
                detail.get('error')
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

def sync_all(token):
    """
    Synchronisation complète classique (version originale)
    
    Étapes:
    1. Récupère tous les torrents de base
    2. Récupère tous les détails
    
    Usage: Pour première synchronisation complète
    Temps estimé: 4-6 heures pour 4000+ torrents
    """
    logging.info("📥 Synchronisation complète classique...")
    
    # Étape 1: Tous les torrents
    total = asyncio.run(fetch_all_torrents(token))
    logging.info(f"✅ {total} torrents récupérés")
    
    # Étape 2: Tous les détails
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        torrent_ids = [row[0] for row in c.fetchall()]
    
    logging.info(f"🔄 Récupération des détails pour {len(torrent_ids)} torrents...")
    processed = asyncio.run(fetch_all_torrent_details(token, torrent_ids))
    logging.info(f"✅ Synchronisation complète terminée ! {processed} détails traités")

def sync_all_v2(token):
    """
    Synchronisation rapide optimisée (sync-fast)
    
    Version améliorée de sync_all avec:
    - Contrôle dynamique de concurrence
    - Pool de connexions optimisé
    - Reprise automatique possible
    - Statistiques temps réel
    
    Usage: Synchronisation complète optimisée
    Temps estimé: 7-10 minutes pour 4000+ torrents
    """
    logging.info("🚀 Synchronisation rapide démarrée...")
    
    # Étape 1: Récupérer tous les torrents (identique)
    total = asyncio.run(fetch_all_torrents(token))
    logging.info(f"✅ {total} torrents synchronisés")
    
    # Étape 2: Récupération optimisée des détails
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        torrent_ids = [row[0] for row in c.fetchall()]
    
    logging.info(f"🔄 Récupération optimisée des détails pour {len(torrent_ids)} torrents...")
    processed = asyncio.run(fetch_all_torrent_details_v2(token, torrent_ids, resumable=True))
    logging.info(f"🎯 Synchronisation rapide terminée ! {processed} détails traités")

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
        
        # Téléchargements actifs
        c.execute('''
            SELECT COUNT(*) FROM torrent_details
            WHERE status IN ('downloading', 'queued', 'waiting_files_selection')
        ''')
        active_count = c.fetchone()[0]
        
        # Torrents en erreur (pour retry)
        c.execute('''
            SELECT COUNT(*) FROM torrent_details
            WHERE status = 'error' OR error IS NOT NULL
        ''')
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
    Synchronisation intelligente - Mode recommandé pour usage quotidien
    
    Fonctionnalités:
    - ✅ Détecte uniquement les changements nécessaires
    - ✅ Retry automatique des torrents en erreur  
    - ✅ Analyse pré-sync avec résumé détaillé
    - ✅ Performance optimisée (15-50 torrents/s)
    - ✅ Résumé post-sync avec recommandations
    
    Usage: python src/main.py --sync-smart
    Temps typique: 30s - 2 minutes
    """
    logging.info("🧠 Synchronisation intelligente démarrée...")
    
    # Analyser les changements avant de commencer
    summary = get_smart_update_summary()
    
    # Afficher le résumé des changements détectés
    logging.info("📊 Analyse des changements :")
    if summary['new_torrents'] > 0:
        logging.info(f"   🆕 Nouveaux torrents sans détails : {summary['new_torrents']}")
    if summary['active_downloads'] > 0:
        logging.info(f"   ⬇️  Téléchargements actifs : {summary['active_downloads']}")
    if summary['error_retry'] > 0:
        logging.info(f"   🔄 Torrents en erreur (retry) : {summary['error_retry']}")
    if summary['old_updates'] > 0:
        logging.info(f"   📅 Torrents anciens (>7j) : {summary['old_updates']}")
    
    # Obtenir la liste des torrents à mettre à jour
    torrent_ids = get_torrents_needing_update()
    
    if not torrent_ids:
        logging.info("✅ Rien à synchroniser, tout est à jour !")
        return
    
    total_changes = len(torrent_ids)
    logging.info(f"🎯 Total : {total_changes} torrents nécessitent une mise à jour")
    
    # Traiter les mises à jour avec mesure du temps
    start_time = time.time()
    processed = asyncio.run(fetch_all_torrent_details_v2(token, torrent_ids))
    end_time = time.time()
    
    # Statistiques finales
    duration = end_time - start_time
    rate = processed / duration if duration > 0 else 0
    
    logging.info(f"✅ Synchronisation intelligente terminée !")
    logging.info(f"   📊 {processed} détails mis à jour en {duration:.1f}s ({rate:.1f}/s)")
    
    # Afficher un résumé final
    display_final_summary()

def sync_resume(token):
    """
    Reprendre une synchronisation interrompue à partir du point d'arrêt
    
    Utilise les fichiers de progression sauvegardés pour reprendre
    exactement là où la synchronisation s'était arrêtée.
    
    Usage: python src/main.py --resume
    """
    logging.info("⏮️  Reprise de synchronisation...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        all_ids = [row[0] for row in c.fetchall()]
    
    processed = asyncio.run(fetch_all_torrent_details_v2(token, all_ids, resumable=True))
    logging.info(f"✅ Reprise terminée ! {processed} détails traités")

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
        return
        
    logging.info(f"🔄 Synchronisation des détails pour {len(torrent_ids)} torrents...")
    processed = asyncio.run(fetch_all_torrent_details(token, torrent_ids))
    logging.info(f"✅ Détails synchronisés pour {processed} torrents.")

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
    logging.info("📋 Synchronisation des torrents de base uniquement...")
    
    total = asyncio.run(fetch_all_torrents(token))
    
    if total > 0:
        logging.info(f"✅ Synchronisation terminée ! {total} torrents enregistrés dans la table 'torrents'")
        
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
            
            # Répartition par statut (top 5)
            c.execute("""
                SELECT COALESCE(td.status, t.status, 'inconnu') as status, COUNT(*) as count
                FROM torrents t
                LEFT JOIN torrent_details td ON t.id = td.id
                GROUP BY COALESCE(td.status, t.status)
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
        c.execute("SELECT status, COUNT(*) FROM torrents GROUP BY status ORDER BY COUNT(*) DESC")
        torrent_status = c.fetchall()
        
        c.execute("SELECT status, COUNT(*) FROM torrent_details GROUP BY status ORDER BY COUNT(*) DESC")
        detail_status = c.fetchall()
        
        # === TAILLES ET VOLUMES ===
        c.execute("SELECT SUM(bytes), AVG(bytes), MIN(bytes), MAX(bytes) FROM torrents WHERE bytes > 0")
        size_stats = c.fetchone()
        total_size, avg_size, min_size, max_size = size_stats if size_stats and size_stats[0] else (0, 0, 0, 0)
        
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
            print(f"   📊 Taille moyenne     : {format_size(avg_size) if avg_size else 'N/A'}")
            print(f"   🔻 Plus petit         : {format_size(min_size) if min_size else 'N/A'}")
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
        
        c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'downloading'")
        downloading = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'error'")
        errors = c.fetchone()[0] or 0
        
        coverage = (details / total * 100) if total > 0 else 0
        
        print(f"📊 {total:,} torrents | {details:,} détails ({coverage:.1f}%) | "
              f"⬇️ {downloading} en cours | ❌ {errors} erreurs")

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

def diagnose_token():
    """
    Diagnostique le token pour identifier les problèmes de configuration
    
    Analyse:
    - Variables d'environnement
    - Fichiers de configuration
    - Validation du format
    - Test Header Injection
    
    Usage: Fonction utilitaire pour debug
    """
    import re
    
    print("\n🔍 DIAGNOSTIC DU TOKEN REAL-DEBRID")
    print("=" * 60)
    
    load_env_file()
    
    # Test variable d'environnement
    env_token = os.getenv('RD_TOKEN')
    if env_token:
        print(f"📌 TOKEN VARIABLE D'ENVIRONNEMENT")
        print(f"   Longueur: {len(env_token)} caractères")
        print(f"   Représentation: {repr(env_token)}")
        print(f"   Contient \\n: {'OUI' if '\\n' in env_token else 'NON'}")
        print(f"   Contient \\r: {'OUI' if '\\r' in env_token else 'NON'}")
        print(f"   Après strip(): {repr(env_token.strip())}")
        
        # Validation format
        is_valid = re.match(r'^[A-Za-z0-9_-]+$', env_token.strip())
        print(f"   Format valide: {'✅ OUI' if is_valid else '❌ NON'}")
    else:
        print("📌 TOKEN VARIABLE D'ENVIRONNEMENT: Absent")
    
    # Test fichier config
    config_file = os.path.join(os.path.dirname(__file__), "../config/rd_token.conf")
    if os.path.exists(config_file):
        print(f"\n📁 TOKEN FICHIER CONFIG")
        
        # Lecture en mode binaire pour voir tous les caractères
        with open(config_file, 'rb') as f:
            file_content = f.read()
        
        print(f"   Taille fichier: {len(file_content)} bytes")
        print(f"   Contenu brut: {repr(file_content)}")
        
        try:
            text_content = file_content.decode('utf-8')
            print(f"   Contenu texte: {repr(text_content)}")
            print(f"   Après strip(): {repr(text_content.strip())}")
                
        except UnicodeDecodeError as e:
            print(f"   ❌ Erreur d'encodage: {e}")
    else:
        print(f"\n📁 TOKEN FICHIER CONFIG: {config_file} n'existe pas")
    
    # Test token final (simulation de load_token)
    print(f"\n🔬 TEST LOAD_TOKEN()")
    
    try:
        token = load_token()
        print(f"   ✅ Token chargé avec succès")
        print(f"   Longueur: {len(token)} caractères")
        print(f"   Représentation: {repr(token)}")
        
        # Test validation regex
        is_valid = re.match(r'^[A-Za-z0-9_-]+$', token)
        print(f"   Format valide: {'✅ OUI' if is_valid else '❌ NON'}")
        
        # Test de l'erreur Header Injection
        print(f"\n🚨 TEST HEADER INJECTION")
        test_header_value = f"Bearer {token}"
        
        dangerous_chars = ['\n', '\r', '\r\n']
        header_safe = True
        
        for dangerous_char in dangerous_chars:
            if dangerous_char in test_header_value:
                print(f"   ❌ Caractère dangereux détecté: {repr(dangerous_char)}")
                header_safe = False
        
        if header_safe:
            print(f"   ✅ Header Authorization sûr")
        else:
            print(f"   ❌ Header Authorization DANGEREUX")
        
    except SystemExit:
        print("   ❌ Échec du chargement du token")
    
    print(f"\n" + "=" * 60)

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
        print("  5. 🚀 Sync rapide complet")
        print("  6. 📋 Torrents uniquement (ultra-rapide)")
        print("  7. 📖 Sync classique complet")
        print("  8. ⏮️  Reprendre sync interrompu")
        
        print("\n🔧 MAINTENANCE")
        print("  9. 🔄 Détails uniquement")
        print(" 10. ❌ Retry torrents en erreur")
        print(" 11. ⬇️  Mise à jour téléchargements actifs")
        print(" 12. 🗑️  Vider la base de données")
        print(" 13. 🔍 Diagnostic du token")
        
        print("\n❓ AIDE & SORTIE")
        print(" 14. 💡 Guide de choix rapide")
        print(" 15. 🏃 Mode commande (passer aux arguments)")
        print("  0. 🚪 Quitter")
        
        print("\n" + "─" * 60)
        
        try:
            choice = input("👉 Votre choix (0-15) : ").strip()
            
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
                    confirm = input("\n⚠️  Sync classique (peut prendre plusieurs heures). Continuer ? (o/N): ")
                    if confirm.lower() in ['o', 'oui', 'y', 'yes']:
                        sync_all(token)
                        input("\n✅ Appuyez sur Entrée pour continuer...")
                    else:
                        print("❌ Annulé.")
                        input("📋 Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "8":
                token = get_token()
                if token:
                    print("\n⏮️  Reprise de la synchronisation...")
                    sync_resume(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "9":
                token = get_token()
                if token:
                    print("\n🔄 Mise à jour des détails uniquement...")
                    sync_details_only(token)
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "10":
                token = get_token()
                if token:
                    print("\n❌ Retry des torrents en erreur...")
                    sync_details_only(token, status_filter="error")
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "11":
                token = get_token()
                if token:
                    print("\n⬇️  Mise à jour des téléchargements actifs...")
                    sync_details_only(token, status_filter="downloading")
                    input("\n✅ Appuyez sur Entrée pour continuer...")
                else:
                    input("\n❌ Token manquant. Appuyez sur Entrée pour continuer...")
                    
            elif choice == "12":
                confirm = input("\n⚠️  ATTENTION : Vider complètement la base de données ? (tapez 'SUPPRIMER'): ")
                if confirm == "SUPPRIMER":
                    clear_database()
                    input("\n🗑️  Base vidée. Appuyez sur Entrée pour continuer...")
                else:
                    print("❌ Annulé.")
                    input("📋 Appuyez sur Entrée pour continuer...")
                    
            elif choice == "13":
                print("\n🔍 Diagnostic du token en cours...")
                diagnose_token()
                input("\n🔧 Appuyez sur Entrée pour continuer...")
                
            elif choice == "14":
                show_quick_guide()
                input("\n💡 Appuyez sur Entrée pour continuer...")
                
            elif choice == "15":
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

def show_quick_guide():
    """
    Guide de choix rapide pour aider les utilisateurs à choisir les bonnes options
    
    Recommandations par cas d'usage:
    - 🥇 Première utilisation
    - 📅 Usage quotidien  
    - 🔧 Maintenance
    - ⚡ Vitesses approximatives
    - ❓ En cas de doute
    """
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "💡 GUIDE DE CHOIX" + " " * 18 + "║")
    print("╚" + "═" * 58 + "╝")
    
    print("\n🎯 UTILISATION RECOMMANDÉE :")
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 🥇 PREMIÈRE FOIS :                                     │")
    print("│    → Choix 5 : Sync rapide complet (7-10 min)         │")
    print("│                                                         │")
    print("│ 📅 USAGE QUOTIDIEN :                                   │")
    print("│    → Choix 2 : Stats compactes (<1s)                  │")
    print("│    → Choix 4 : Sync intelligent (30s-2min)            │")
    print("│                                                         │")
    print("│ 🔧 MAINTENANCE :                                        │")
    print("│    → Choix 1 : Stats complètes + recommandations      │")
    print("│    → Choix 3 : Diagnostic si problèmes                │")
    print("│    → Choix 10: Retry erreurs si nécessaire            │")
    print("└─────────────────────────────────────────────────────────┘")
    
    print("\n⚡ VITESSES APPROXIMATIVES :")
    print("  📊 Stats (1-2)     : <1 seconde")
    print("  🧠 Sync smart (4)  : 30s - 2 minutes")
    print("  🚀 Sync rapide (5) : 7-10 minutes")
    print("  📋 Torrents (6)    : 10-30 secondes")
    print("  📖 Sync classique  : 4-6 heures (non recommandé)")
    
    print("\n❓ EN CAS DE DOUTE :")
    print("  👉 Commencez par le choix 2 (stats compactes)")
    print("  👉 Puis choix 4 (sync intelligent)")
    print("  👉 Choix 1 pour analyse détaillée si besoin")

def get_token():
    """
    Récupère le token avec vérification et messages d'aide
    
    Returns:
        str/None: Token valide ou None si non trouvé
    """
    load_env_file()  # Charger les variables d'environnement
    
    # Essayer de récupérer le token
    token = os.getenv('RD_TOKEN')
    if not token:
        try:
            with open('config/rd_token.conf', 'r') as f:
                token = f.read().strip()
        except FileNotFoundError:
            pass
    
    if not token:
        print("\n❌ ERREUR : Token Real-Debrid non trouvé !")
        print("🔧 Veuillez configurer votre token :")
        print("   • Variable d'environnement : export RD_TOKEN='votre_token'")
        print("   • Fichier config : cp config/rd_token.conf.example config/rd_token.conf")
        print("   • Fichier .env : cp .env.example .env")
    
    return token

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
    load_env_file()  # Charger les variables d'environnement au début
    
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
    
    # Arguments classiques
    parser.add_argument('--sync-all', action='store_true', 
                       help="🔄 Synchronisation complète classique (4-6h)")
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
    
    # Arguments optimisés (nouvelles fonctionnalités)
    parser.add_argument('--sync-fast', action='store_true', 
                       help="🚀 Synchronisation rapide optimisée (7-10min)")
    parser.add_argument('--sync-smart', action='store_true', 
                       help="🧠 Synchronisation intelligente - changements uniquement (30s-2min)")
    parser.add_argument('--resume', action='store_true', 
                       help="⏮️  Reprendre une synchronisation interrompue")
    parser.add_argument('--torrents-only', action='store_true', 
                       help="📋 Synchroniser uniquement les torrents de base sans détails (10-30s)")
    parser.add_argument('--diagnose-errors', action='store_true', 
                       help="🔍 Diagnostic détaillé des torrents en erreur avec suggestions")
    parser.add_argument('--diagnose-token', action='store_true', 
                       help="🔍 Diagnostic complet du token Real-Debrid (debug)")
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
            
        elif args.diagnose_token:
            diagnose_token()
            
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
            
        elif args.sync_all:
            sync_all(token)
            
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
