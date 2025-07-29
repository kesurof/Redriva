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
    """Charge les variables d'environnement depuis le fichier .env"""
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

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Interruption propre
stop_requested = False
def handle_sigint(signum, frame):
    global stop_requested
    logging.warning("Interruption clavier reçue (CTRL+C), arrêt propre...")
    stop_requested = True

signal.signal(signal.SIGINT, handle_sigint)

# Configuration via variables d'environnement avec valeurs par défaut
RD_API_URL = "https://api.real-debrid.com/rest/1.0/torrents"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/redriva.db'))
MAX_CONCURRENT = int(os.getenv('RD_MAX_CONCURRENT', '50'))
BATCH_SIZE = int(os.getenv('RD_BATCH_SIZE', '250'))
QUOTA_WAIT_TIME = int(os.getenv('RD_QUOTA_WAIT', '60'))
TORRENT_WAIT_TIME = int(os.getenv('RD_TORRENT_WAIT', '10'))

def load_token():
    token = os.environ.get("RD_TOKEN")
    if not token:
        config_path = os.path.join(os.path.dirname(__file__), "../config/rd_token.conf")
        if os.path.exists(config_path):
            with open(config_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        token = line
                        break
    if not token:
        logging.error("Token Real-Debrid introuvable.")
        sys.exit(1)
    return token

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS torrents (
            id TEXT PRIMARY KEY,
            filename TEXT,
            status TEXT,
            bytes INTEGER,
            added_on TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS torrent_details (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            size INTEGER,
            files_count INTEGER,
            added TEXT,
            downloaded INTEGER,
            speed INTEGER,
            progress REAL,
            hash TEXT,
            original_filename TEXT,
            host TEXT,
            split INTEGER,
            links TEXT,
            ended TEXT,
            error TEXT,
            links_count INTEGER,
            folder TEXT,
            priority TEXT,
            custom1 TEXT
        )''')
        conn.commit()

async def api_request(session, url, headers, params=None, max_retries=3):
    """Fonction générique pour les appels API avec gestion d'erreurs"""
    for attempt in range(max_retries):
        if stop_requested:
            return None
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 401 or resp.status == 403:
                    logging.error("Token Real-Debrid invalide ou expiré.")
                    sys.exit(1)
                if resp.status == 404:
                    return None
                if resp.status == 429:
                    wait_time = QUOTA_WAIT_TIME if params else TORRENT_WAIT_TIME
                    logging.warning(f"Quota API dépassé, attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            if attempt == max_retries - 1:
                logging.error(f"Erreur API après {max_retries} tentatives: {e}")
                return None
            await asyncio.sleep(2 ** attempt)  # Backoff exponentiel
    return None

def upsert_torrent_detail(detail):
    if not detail or not detail.get('id'):
        return
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO torrent_details
            (id, name, status, size, files_count, added, downloaded, speed, progress, hash, original_filename, host, split, links, ended, error, links_count, folder, priority, custom1)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                detail.get('id'),
                detail.get('filename') or detail.get('name'),
                detail.get('status'),
                detail.get('bytes'),
                len(detail.get('files', [])),
                detail.get('added'),
                detail.get('downloaded'),
                detail.get('speed'),
                detail.get('progress'),
                detail.get('hash'),
                detail.get('original_filename'),
                detail.get('host'),
                detail.get('split'),
                ",".join(detail.get('links', [])) if detail.get('links') else None,
                detail.get('ended'),
                detail.get('error'),
                detail.get('links_count'),
                detail.get('folder'),
                detail.get('priority'),
                None
            )
        )
        conn.commit()

def upsert_torrent(t):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO torrents (id, filename, status, bytes, added_on)
            VALUES (?, ?, ?, ?, ?)''',
            (t.get('id'), t.get('filename'), t.get('status'), t.get('bytes'), t.get('added'),)
        )
        conn.commit()

async def fetch_all_torrents(token):
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
                
            for t in torrents:
                upsert_torrent(t)
            total += len(torrents)
            logging.info(f"Page {page}: {len(torrents)} torrents (total: {total})")
            page += 1
    return total

async def fetch_torrent_detail(session, token, torrent_id):
    url = f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    detail = await api_request(session, url, headers)
    if detail:
        logging.info(f"Détail récupéré pour {torrent_id}")
        upsert_torrent_detail(detail)
    return detail

async def fetch_all_torrent_details(token, torrent_ids, max_concurrent=MAX_CONCURRENT):
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

def show_stats():
    """Affiche les statistiques complètes et détaillées de la base de données"""
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
            print(f"\n📈 RÉPARTITION PAR STATUT (Torrents)")
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
        
        # Recommandations
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

def sync_details_only(token, status_filter=None):
    """Synchronise uniquement les détails des torrents existants"""
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
        
    logging.info(f"Synchronisation des détails pour {len(torrent_ids)} torrents...")
    processed = asyncio.run(fetch_all_torrent_details(token, torrent_ids))
    logging.info(f"Détails synchronisés pour {processed} torrents.")

def sync_all(token):
    """Synchronisation complète"""
    total = asyncio.run(fetch_all_torrents(token))
    logging.info(f"Synchronisation terminée. {total} torrents enregistrés.")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        torrent_ids = [row[0] for row in c.fetchall()]
    
    logging.info(f"Récupération des détails de {len(torrent_ids)} torrents...")
    processed = asyncio.run(fetch_all_torrent_details(token, torrent_ids))
    logging.info(f"Détails récupérés pour {processed} torrents.")

def clear_database():
    """Vide complètement la base de données"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM torrent_details")
            details_deleted = c.rowcount
            c.execute("DELETE FROM torrents")
            torrents_deleted = c.rowcount
            conn.commit()
            
        print(f"✅ Base de données vidée avec succès:")
        print(f"   - {torrents_deleted} torrents supprimés")
        print(f"   - {details_deleted} détails supprimés")
        
    except Exception as e:
        logging.error(f"Erreur lors du vidage de la base : {e}")

# === NOUVELLES FONCTIONS OPTIMISÉES ===

class DynamicRateLimiter:
    def __init__(self, initial_concurrent=20, max_concurrent=80):
        self.concurrent = initial_concurrent
        self.max_concurrent = max_concurrent
        self.success_count = 0
        self.error_count = 0
        self.last_adjustment = time.time()
        
    def adjust_concurrency(self, success=True):
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            
        if (self.success_count + self.error_count) % 50 == 0 or time.time() - self.last_adjustment > 30:
            error_rate = self.error_count / max(1, self.success_count + self.error_count)
            
            if error_rate < 0.05:
                self.concurrent = min(self.max_concurrent, int(self.concurrent * 1.2))
                logging.info(f"📈 Concurrence augmentée à {self.concurrent}")
            elif error_rate > 0.15:
                self.concurrent = max(5, int(self.concurrent * 0.7))
                logging.info(f"📉 Concurrence réduite à {self.concurrent}")
                
            self.last_adjustment = time.time()
            self.success_count = self.error_count = 0
            
    def get_semaphore(self):
        return asyncio.Semaphore(self.concurrent)

def save_progress(processed_ids, filename="data/sync_progress.json"):
    """Sauvegarde la progression"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        json.dump({
            'processed_ids': list(processed_ids),
            'timestamp': time.time()
        }, f)

def load_progress(filename="data/sync_progress.json"):
    """Charge la progression précédente"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            if time.time() - data['timestamp'] < 21600:  # 6 heures
                return set(data['processed_ids'])
    except:
        pass
    return set()

def get_torrents_needing_update():
    """Torrents nécessitant une mise à jour (version basique)"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT t.id FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE td.id IS NULL 
               OR (td.status IN ('downloading', 'queued', 'waiting_files_selection'))
               OR datetime('now') - datetime(t.added_on) > 7
        ''')
        return [row[0] for row in c.fetchall()]

def get_smart_update_summary():
    """Analyse intelligente des torrents nécessitant une mise à jour"""
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

async def fetch_all_torrent_details_v2(token, torrent_ids, resumable=False):
    """Version optimisée de fetch_all_torrent_details"""
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
            semaphore = rate_limiter.get_semaphore()
            async with semaphore:
                result = await fetch_torrent_detail(session, token, tid)
                success = result is not None
                rate_limiter.adjust_concurrency(success)
                
                if success:
                    nonlocal total_processed
                    total_processed += 1
                    processed_ids.add(tid)
                    
                    # Stats temps réel + sauvegarde
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
            
            # Pause adaptative
            if i + chunk_size < len(remaining_ids):
                pause = max(3, 20 - rate_limiter.concurrent * 0.2)
                logging.info(f"⏸️  Pause {pause:.1f}s...")
                await asyncio.sleep(pause)
    
    elapsed = time.time() - start_time
    processed_new = total_processed - len(set(processed_ids) - processed_ids)
    logging.info(f"🎉 Terminé ! {processed_new} nouveaux détails en {elapsed/60:.1f}min "
                 f"({processed_new/elapsed:.1f} torrents/s)")
    
    # Nettoyer le fichier de progression
    if resumable and os.path.exists("data/sync_progress.json"):
        os.remove("data/sync_progress.json")
    
    return total_processed

def sync_all_v2(token):
    """Version optimisée de sync_all"""
    logging.info("🚀 Synchronisation rapide démarrée...")
    
    # Étape 1: Récupérer tous les torrents (inchangé)
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

def sync_smart(token):
    """Synchronisation intelligente (seulement ce qui a changé)"""
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

def display_final_summary():
    """Affiche un résumé des données synchronisées"""
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
                    print(f"   • {status} : {count} ({percentage:.1f}%)")
                    
    except Exception as e:
        logging.warning(f"Impossible d'afficher le résumé : {e}")

def sync_resume(token):
    """Reprendre une synchronisation interrompue"""
    logging.info("⏮️  Reprise de synchronisation...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM torrents")
        all_ids = [row[0] for row in c.fetchall()]
    
    processed = asyncio.run(fetch_all_torrent_details_v2(token, all_ids, resumable=True))
    logging.info(f"✅ Reprise terminée ! {processed} détails traités")

def sync_torrents_only(token):
    """Synchronisation uniquement des torrents de base (sans détails)"""
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
                print(f"   {status}: {count}")
    else:
        logging.info("ℹ️  Aucun torrent trouvé ou synchronisé")

def format_size(bytes_size):
    """Convertit les bytes en format lisible"""
    if not bytes_size or bytes_size == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} EB"

def get_status_emoji(status):
    """Retourne un emoji selon le statut"""
    emoji_map = {
        'downloaded': '✅',
        'downloading': '⬇️',
        'queued': '⏳',
        'error': '❌',
        'waiting_files_selection': '📋',
        'magnet_error': '🧲',
        'virus': '🦠',
        'dead': '💀',
        'compressing': '📦',
        'uploading': '⬆️'
    }
    return emoji_map.get(status, '❓')

def show_stats_compact():
    """Version compacte des statistiques pour usage fréquent"""
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

def analyze_error_type(error_msg, status):
    """Analyse le type d'erreur basé sur le message"""
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
    """Propose une solution basée sur le type d'erreur"""
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
    """Diagnostique détaillé des torrents en erreur"""
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
        
        for i, (torrent_id, name, status, error, progress, filename, added_on, bytes_size) in enumerate(errors, 1):
            print(f"\n❌ ERREUR #{i}")
            print(f"   🆔 ID             : {torrent_id}")
            print(f"   📁 Nom            : {name or filename or 'N/A'}")
            print(f"   📊 Statut         : {status}")
            print(f"   ⚠️  Message d'erreur: {error or 'Aucun message spécifique'}")
            print(f"   📈 Progression    : {progress or 0}%")
            print(f"   📅 Ajouté le      : {added_on}")
            print(f"   💾 Taille         : {format_size(bytes_size) if bytes_size else 'N/A'}")
            
            # Analyse du type d'erreur
            error_type = analyze_error_type(error, status)
            print(f"   🔬 Type d'erreur  : {error_type}")
            
            # Suggestion de correction
            suggestion = get_error_suggestion(error, status)
            print(f"   💡 Suggestion     : {suggestion}")
            print("-" * 80)
        
        # Résumé des types d'erreurs
        print(f"\n📊 RÉSUMÉ DES TYPES D'ERREURS")
        error_types = {}
        for _, _, _, error, _, _, _, _ in errors:
            error_type = analyze_error_type(error, None)
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {error_type} : {count}")
        
        print(f"\n💡 ACTIONS RECOMMANDÉES :")
        print(f"   🔄 Retry automatique    : python src/main.py --sync-smart")
        print(f"   🎯 Retry forcé          : python src/main.py --details-only --status error")
        print(f"   📊 Vérifier l'état      : python src/main.py --stats")

def main():
    parser = argparse.ArgumentParser(description="Redriva - Sync Real-Debrid vers SQLite")
    parser.add_argument('--sync-all', action='store_true', help="Synchroniser tous les torrents")
    parser.add_argument('--details-only', action='store_true', help="Synchroniser uniquement les détails des torrents existants")
    parser.add_argument('--status', help="Filtrer par status (downloaded, error, etc.)")
    parser.add_argument('--stats', action='store_true', help="Afficher les statistiques de la base")
    parser.add_argument('--compact', action='store_true', help="Affichage compact des statistiques")
    parser.add_argument('--clear', action='store_true', help="Vider complètement la base de données")
    
    # === NOUVELLES OPTIONS OPTIMISÉES ===
    parser.add_argument('--sync-fast', action='store_true', help="🚀 Synchronisation rapide (version optimisée)")
    parser.add_argument('--sync-smart', action='store_true', help="🧠 Synchronisation intelligente (seulement les changements)")
    parser.add_argument('--resume', action='store_true', help="⏮️  Reprendre une synchronisation interrompue")
    parser.add_argument('--torrents-only', action='store_true', help="📋 Synchroniser uniquement les torrents de base (sans détails)")
    parser.add_argument('--diagnose-errors', action='store_true', help="🔍 Diagnostique détaillé des torrents en erreur")
    
    args = parser.parse_args()

    token = load_token()
    init_db()

    try:
        if args.clear:
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
        elif args.torrents_only:
            sync_torrents_only(token)   # NOUVELLE OPTION
        elif args.diagnose_errors:
            diagnose_errors()  # DIAGNOSTIC DES ERREURS
        elif args.sync_fast:
            sync_all_v2(token)  # NOUVELLE VERSION RAPIDE
        elif args.sync_smart:
            sync_smart(token)   # NOUVELLE VERSION INTELLIGENTE
        elif args.resume:
            sync_resume(token)  # NOUVELLE VERSION RESUMABLE
        elif args.details_only:
            sync_details_only(token, args.status)  # ANCIENNE VERSION
        elif args.sync_all:
            sync_all(token)     # ANCIENNE VERSION
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logging.warning("Arrêt manuel par l'utilisateur.")
    except Exception as e:
        logging.error(f"Erreur inattendue : {e}")

if __name__ == "__main__":
    main()