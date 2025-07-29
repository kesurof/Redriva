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
    """Affiche les statistiques de la base de données"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM torrents")
        total_torrents = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM torrent_details")
        total_details = c.fetchone()[0]
        
        c.execute("SELECT status, COUNT(*) FROM torrents GROUP BY status")
        status_counts = dict(c.fetchall())
        
        print(f"\n📊 Statistiques Redriva:")
        print(f"   Torrents: {total_torrents}")
        print(f"   Détails: {total_details}")
        print(f"   Status: {status_counts}")

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
    """Torrents nécessitant une mise à jour"""
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
    
    torrent_ids = get_torrents_needing_update()
    if not torrent_ids:
        logging.info("✅ Rien à synchroniser, tout est à jour !")
        return
        
    logging.info(f"🎯 {len(torrent_ids)} torrents nécessitent une mise à jour")
    processed = asyncio.run(fetch_all_torrent_details_v2(token, torrent_ids))
    logging.info(f"✅ Synchronisation intelligente terminée ! {processed} détails mis à jour")

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

def main():
    parser = argparse.ArgumentParser(description="Redriva - Sync Real-Debrid vers SQLite")
    parser.add_argument('--sync-all', action='store_true', help="Synchroniser tous les torrents")
    parser.add_argument('--details-only', action='store_true', help="Synchroniser uniquement les détails des torrents existants")
    parser.add_argument('--status', help="Filtrer par status (downloaded, error, etc.)")
    parser.add_argument('--stats', action='store_true', help="Afficher les statistiques de la base")
    parser.add_argument('--clear', action='store_true', help="Vider complètement la base de données")
    
    # === NOUVELLES OPTIONS OPTIMISÉES ===
    parser.add_argument('--sync-fast', action='store_true', help="🚀 Synchronisation rapide (version optimisée)")
    parser.add_argument('--sync-smart', action='store_true', help="🧠 Synchronisation intelligente (seulement les changements)")
    parser.add_argument('--resume', action='store_true', help="⏮️  Reprendre une synchronisation interrompue")
    parser.add_argument('--torrents-only', action='store_true', help="📋 Synchroniser uniquement les torrents de base (sans détails)")
    
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
            show_stats()
        elif args.torrents_only:
            sync_torrents_only(token)   # NOUVELLE OPTION
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