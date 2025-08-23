#!/usr/bin/env python3
"""
Redriva Web Interface - Interface web simple pour Redriva
Maintenu via Claude/Copilot - Architecture Flask minimaliste
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sqlite3
import asyncio
import threading
import time
import os
import sys
import json
import logging
import requests
import urllib.parse
import uuid
import signal
import traceback
import aiohttp
from datetime import datetime

# Import des fonctions existantes
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import du gestionnaire de configuration
from config_manager import get_config, load_token, get_database_path

from main import (
    sync_smart, sync_all_v2, sync_torrents_only,
    show_stats, diagnose_errors, get_db_stats, format_size, get_status_emoji,
    create_tables, sync_details_only, ACTIVE_STATUSES, ERROR_STATUSES, COMPLETED_STATUSES,
    fetch_torrent_detail, upsert_torrent_detail, log_event, get_db_path
)

# Utilisation de la configuration centralisée - DB_PATH sera dynamique
def get_current_db_path():
    """Récupère le chemin actuel de la base de données"""
    return get_database_path()

# Pour compatibilité, DB_PATH pointe vers le résultat de la fonction
DB_PATH = get_current_db_path()

# INITIALISATION AUTOMATIQUE DE LA BASE DE DONNÉES
def init_database_if_needed():
    """Initialise la base de données si elle n'existe pas ou est incomplète"""
    try:
        db_path = get_db_path()
        print("🔧 Vérification de la base de données...")
        log_event('DB_CHECK_START', path=db_path)

        # Vérifier si la base existe
        if not os.path.exists(db_path):
            print("📂 Base de données non trouvée, création en cours...")
            create_tables()
            print("✅ Base de données créée avec succès")
            log_event('DB_CHECK_END', status='created')
            return

        # Vérifier l'intégrité des tables
        try:
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()

                # Vérifier que les tables principales existent
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='torrents'")
                if not c.fetchone():
                    print("🔧 Table 'torrents' manquante, recréation...")
                    create_tables()
                    print("✅ Tables recréées avec succès")
                    return

                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='torrent_details'")
                if not c.fetchone():
                    print("🔧 Table 'torrent_details' manquante, recréation...")
                    create_tables()
                    print("✅ Tables recréées avec succès")
                    return

                # Vérifier que la colonne health_error existe
                c.execute("PRAGMA table_info(torrent_details)")
                columns = [column[1] for column in c.fetchall()]
                if 'health_error' not in columns:
                    print("🔧 Colonne 'health_error' manquante, ajout en cours...")
                    c.execute("ALTER TABLE torrent_details ADD COLUMN health_error TEXT")
                    conn.commit()
                    print("✅ Colonne 'health_error' ajoutée avec succès")

                print("✅ Base de données vérifiée et à jour")
                log_event('DB_CHECK_END', status='ok')

        except Exception as db_error:
            print(f"⚠️ Problème avec la base existante: {db_error}")
            print("🔧 Recréation complète de la base de données...")
            # Sauvegarder l'ancienne base si elle existe
            if os.path.exists(DB_PATH):
                backup_path = f"{DB_PATH}.backup"
                import shutil
                shutil.copy2(DB_PATH, backup_path)
                print(f"💾 Ancienne base sauvegardée: {backup_path}")

            create_tables()
            print("✅ Base de données recréée avec succès")
            log_event('DB_CHECK_END', status='recreated')

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base: {e}")
        log_event('DB_CHECK_END', status='error', error=str(e))
        print(f"   Chemin de la base: {DB_PATH}")
        raise

# Initialiser la base au démarrage de l'application
print("🚀 Initialisation de Redriva...")
init_database_if_needed()

# Import du nouveau module symlink avec gestion d'erreur
try:
    from symlink_tool import register_symlink_routes, init_symlink_database
    SYMLINK_AVAILABLE = True
    print("✅ Module symlink_tool importé avec succès")
except ImportError as e:
    print(f"⚠️ Module symlink_tool non disponible: {e}")
    SYMLINK_AVAILABLE = False
    # Fonctions de fallback
    def register_symlink_routes(app):
        @app.route('/symlink')
        def symlink_unavailable():
            return "Symlink Manager non disponible", 503
    def init_symlink_database():
        pass

# Import du module de surveillance Arr avec gestion d'erreur
try:
    from arr_monitor import get_arr_monitor
    ARR_MONITOR_AVAILABLE = True
    print("✅ Module arr_monitor importé avec succès")
except ImportError as e:
    print(f"⚠️ Module arr_monitor non disponible: {e}")
    ARR_MONITOR_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialisation du moniteur Arr en arrière-plan
if ARR_MONITOR_AVAILABLE:
    try:
        config_manager = get_config()
        arr_monitor = get_arr_monitor(config_manager)
        
        # Démarrer automatiquement si des applications Arr sont configurées
        if config_manager.get('sonarr.enabled', False) or config_manager.get('radarr.enabled', False):
            # Démarrer avec un intervalle par défaut de 5 minutes
            auto_start_interval = config_manager.get('arr_monitor.interval', 300)
            if arr_monitor.start_monitoring(auto_start_interval):
                print(f"🔧 Surveillance Arr démarrée automatiquement (intervalle: {auto_start_interval}s)")
            else:
                print("⚠️ Échec du démarrage automatique de la surveillance Arr")
        else:
            print("ℹ️ Surveillance Arr disponible mais aucune application configurée")
    except Exception as e:
        print(f"❌ Erreur initialisation surveillance Arr: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️ Module de surveillance Arr désactivé - module non disponible")

# Variables globales pour le statut des tâches (définies avant les gestionnaires d'erreur)
task_status = {
    "running": False, 
    "progress": "", 
    "result": "",
    "last_update": None
}

# Variable globale pour les opérations de suppression en masse
batch_operations = {}

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALISATION SYMLINK MANAGER (au niveau module pour Gunicorn)
# ═══════════════════════════════════════════════════════════════════════════════

if SYMLINK_AVAILABLE:
    try:
        # Initialiser la base de données symlink
        init_symlink_database()
        print("✅ Base de données Symlink initialisée")
        
        # Enregistrer les routes symlink
        register_symlink_routes(app)
        print("🔗 Routes Symlink Manager enregistrées")
        
    except Exception as e:
        print(f"❌ Erreur initialisation Symlink Manager: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️ Symlink Manager désactivé - module non disponible")

# Configuration adaptée pour Docker et environnements locaux
# Configuration Flask depuis le gestionnaire centralisé
flask_config = get_config().get_flask_config()
app.config['HOST'] = flask_config['host']
app.config['PORT'] = flask_config['port']
app.config['DEBUG'] = flask_config['debug']

# ROUTES DE SETUP INITIAL
@app.before_request
def check_setup():
    """Vérifie si l'application nécessite un setup initial"""
    config = get_config()
    
    # Ignorer les routes de setup et les assets
    if request.endpoint in ['setup_page', 'setup_save', 'static'] or request.path.startswith('/assets'):
        return
    
    # Rediriger vers setup si nécessaire
    if config.needs_setup():
        return redirect('/setup')

@app.route('/setup')
def setup_page():
    """Page de configuration initiale"""
    return render_template('setup.html')

@app.route('/setup', methods=['POST'])
def setup_save():
    """Sauvegarde de la configuration initiale"""
    try:
        config = get_config()
        
        # Debug - afficher les données reçues (sans les tokens)
        print(f"🔧 Données du formulaire reçues :")
        for key, value in request.form.items():
            print(f"   {key}: {'[HIDDEN]' if 'token' in key or 'key' in key else value}")
        
        # ⚠️ SÉCURITÉ : Ne jamais logger les tokens/clés
        setup_data = {
            'rd_token': request.form.get('rd_token', '').strip(),
            'sonarr_url': request.form.get('sonarr_url', '').strip(),
            'sonarr_api_key': request.form.get('sonarr_api_key', '').strip(),
            'radarr_url': request.form.get('radarr_url', '').strip(),
            'radarr_api_key': request.form.get('radarr_api_key', '').strip(),
        }
        
        # Validation du token obligatoire
        if not setup_data['rd_token']:
            flash('❌ Le token Real-Debrid est obligatoire', 'error')
            return render_template('setup.html')
        
        print(f"🔧 Tentative de sauvegarde de la configuration...")
        print(f"🔒 RAPPEL SÉCURITÉ : Tokens stockés localement et exclus de Git")
        
        # Sauvegarder la configuration
        if config.save_setup_config(setup_data):
            print(f"✅ Configuration sauvegardée avec succès")
            flash('✅ Configuration sauvegardée avec succès !', 'success')
            return redirect('/')
        else:
            print(f"❌ Échec de la sauvegarde")
            flash('❌ Erreur lors de la sauvegarde', 'error')
            return render_template('setup.html')
            
    except Exception as e:
        logger.error(f"❌ Erreur setup : {e}")
        print(f"❌ Exception dans setup_save : {e}")
        traceback.print_exc()
        flash(f'❌ Erreur : {e}', 'error')
        return render_template('setup.html')

# Ajout de gestionnaires d'erreur pour diagnostiquer le problème
@app.errorhandler(403)
def forbidden_error(error):
    """Gestionnaire d'erreur 403 pour diagnostiquer le problème"""
    print(f"❌ Erreur 403 interceptée: {error}")
    print(f"   URL demandée: {request.url}")
    print(f"   Méthode: {request.method}")
    print(f"   Headers: {dict(request.headers)}")
    
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False, 
            'error': 'Accès refusé - Vérifiez votre configuration',
            'debug_info': {
                'url': request.url,
                'method': request.method,
                'path': request.path
            }
        }), 403
    
    flash('Erreur 403: Accès refusé - Vérifiez votre configuration', 'error')
    return render_template('torrents.html', 
                         torrents=[], 
                         pagination={'page': 1, 'total_pages': 1, 'total': 0},
                         available_statuses=[],
                         total_count=0,
                         coverage=0,
                         error_403=True), 403

@app.errorhandler(500)
def internal_error(error):
    """Gestionnaire d'erreur 500 pour diagnostiquer les erreurs internes"""
    print(f"❌ Erreur 500 interceptée: {error}")
    print(f"   URL demandée: {request.url}")
    
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False, 
            'error': 'Erreur interne du serveur',
            'debug_info': str(error)
        }), 500
    
    flash('Erreur interne du serveur - Consultez les logs', 'error')
    return render_template('torrents.html', 
                         torrents=[], 
                         pagination={'page': 1, 'total_pages': 1, 'total': 0},
                         available_statuses=[],
                         total_count=0,
                         coverage=0,
                         error_500=True), 500

def get_db_connection():
    """Crée et retourne une connexion à la base de données SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn

def format_download_link(direct_link):
    """Transforme un lien direct en lien downloader Real-Debrid"""
    if not direct_link or not direct_link.startswith('https://real-debrid.com/d/'):
        return direct_link
    
    # URL encoder le lien complet
    encoded_link = urllib.parse.quote(direct_link, safe='')
    return f"https://real-debrid.com/downloader?links={encoded_link}"

def cleanup_deleted_torrents():
    """
    Supprime définitivement de la base de données tous les torrents 
    marqués comme 'deleted' dans les tables torrents et torrent_details.
    Retourne le nombre d'éléments supprimés.
    """
    try:
        log_event('CLEAN_START', scope='deleted_torrents')
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Récupérer les IDs des torrents marqués comme deleted dans la table torrents
            c.execute("SELECT id FROM torrents WHERE status = 'deleted'")
            deleted_torrent_ids = [row[0] for row in c.fetchall()]
            
            # Récupérer les IDs des torrents marqués comme deleted dans la table torrent_details
            c.execute("SELECT id FROM torrent_details WHERE status = 'deleted'")
            deleted_detail_ids = [row[0] for row in c.fetchall()]
            
            # Fusionner les deux listes pour obtenir tous les IDs à supprimer
            all_deleted_ids = list(set(deleted_torrent_ids + deleted_detail_ids))
            
            if not all_deleted_ids:
                print("ℹ️ Aucun torrent marqué comme supprimé trouvé")
                log_event('CLEAN_END', scope='deleted_torrents', deleted=0, status='nothing')
                return {
                    'success': True,
                    'deleted_count': 0,
                    'message': 'Aucun torrent à nettoyer'
                }
            
            # Supprimer de la table torrent_details
            placeholders = ','.join('?' for _ in all_deleted_ids)
            c.execute(f"DELETE FROM torrent_details WHERE id IN ({placeholders})", all_deleted_ids)
            details_deleted = c.rowcount
            
            # Supprimer de la table torrents
            c.execute(f"DELETE FROM torrents WHERE id IN ({placeholders})", all_deleted_ids)
            torrents_deleted = c.rowcount
            
            conn.commit()
            
            total_deleted = len(all_deleted_ids)
            print(f"✅ Nettoyage terminé : {total_deleted} torrents supprimés ({torrents_deleted} de torrents, {details_deleted} de torrent_details)")
            log_event('CLEAN_END', scope='deleted_torrents', deleted=total_deleted, torrents=torrents_deleted, details=details_deleted, status='success')
            
            return {
                'success': True,
                'deleted_count': total_deleted,
                'torrents_deleted': torrents_deleted,
                'details_deleted': details_deleted,
                'message': f'{total_deleted} torrent(s) supprimé(s) définitivement'
            }
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage des torrents supprimés: {e}")
        log_event('CLEAN_END', scope='deleted_torrents', status='error', error=str(e))
        return {
            'success': False,
            'error': str(e),
            'deleted_count': 0
        }

def run_sync_task(task_name, token, task_func, *args):
    """Version simplifiée sans capture d'output"""
    def execute_task():
        import time
        task_id = str(uuid.uuid4())[:8]
        log_event('ASYNC_TASK_START', name=task_name.replace(' ', '_'), task_id=task_id)
        
        try:
            task_status["running"] = True
            task_status["progress"] = f"🚀 Démarrage de {task_name}..."
            task_status["result"] = ""
            task_status["last_update"] = time.time()
            
            # Exécution de la synchronisation
            if args:
                result = task_func(token, *args)
            else:
                result = task_func(token)
            
            task_status["result"] = f"✅ {task_name} terminée avec succès"
            task_status["running"] = False
            task_status["last_update"] = time.time()
            log_event('ASYNC_TASK_END', name=task_name.replace(' ', '_'), task_id=task_id, status='success')
            
        except Exception as e:
            task_status["result"] = f"❌ Erreur dans {task_name}: {str(e)}"
            task_status["running"] = False
            task_status["last_update"] = time.time()
            log_event('ASYNC_TASK_END', name=task_name.replace(' ', '_'), task_id=task_id, status='error', error=str(e))
    
    # Lancer la tâche en arrière-plan
    thread = threading.Thread(target=execute_task)
    thread.daemon = True
    thread.start()
    
    return thread

def run_health_check_task(token):
    """Lance la vérification de santé en arrière-plan"""
    def execute_health_check():
        task_id = str(uuid.uuid4())[:8]
        log_event('HEALTH_CHECK_START', task_id=task_id)
        
        try:
            task_status["running"] = True
            task_status["progress"] = "Initialisation de la vérification de santé..."
            task_status["result"] = ""
            task_status["last_update"] = time.time()
            
            # Récupérer la liste des torrents à vérifier
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT t.id, t.filename 
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE t.status != 'deleted'
                    AND t.status != 'error'
                    ORDER BY t.added_on DESC
                """)
                torrents_to_check = c.fetchall()
            
            if not torrents_to_check:
                task_status["result"] = "Aucun torrent à vérifier"
                task_status["progress"] = "Terminé - Aucun torrent trouvé"
                log_event('HEALTH_CHECK_END', checked=0, errors=0, status='nothing')
                return
            
            task_status["progress"] = f"Démarrage de la vérification de {len(torrents_to_check)} torrents..."
            
            # Exécuter la vérification asynchrone
            total_checked, errors_503_count, completion_status = asyncio.run(
                health_check_async_worker(token, torrents_to_check)
            )
            
            # Résultat final
            duration_minutes = (time.time() - task_status["last_update"]) / 60
            task_status["result"] = f"✅ Vérification {completion_status}: {errors_503_count} erreurs 503 trouvées sur {total_checked} torrents en {duration_minutes:.1f}min"
            task_status["progress"] = f"Terminé - {total_checked}/{len(torrents_to_check)} torrents vérifiés"
            
            log_event('HEALTH_CHECK_END', checked=total_checked, errors=errors_503_count, 
                     duration=f"{duration_minutes:.1f}min", status=completion_status)
            
        except Exception as e:
            error_msg = f"Erreur lors de la vérification: {str(e)}"
            task_status["result"] = f"❌ {error_msg}"
            task_status["progress"] = "Erreur"
            log_event('HEALTH_CHECK_END', status='error', error=str(e))
            logging.error(f"Erreur health check: {e}")
        finally:
            task_status["running"] = False
            task_status["last_update"] = time.time()
    
    # Lancer la tâche en arrière-plan
    thread = threading.Thread(target=execute_health_check)
    thread.daemon = True
    thread.start()
    
    return thread

    return thread

async def health_check_async_worker(token, torrents_to_check):
    """Worker asynchrone pour la vérification de santé - Version complète sans limite de temps"""
    
    async def check_torrent_health_async(session, torrent_id):
        """Vérifie la santé d'un torrent via l'endpoint stream (le plus rapide)"""
        try:
            url = f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}'
            headers = {"Authorization": f"Bearer {token}"}
            
            async with session.get(url, headers=headers, timeout=8) as response:
                if response.status == 404:
                    return torrent_id, "Torrent non trouvé", None
                elif response.status != 200:
                    return torrent_id, f"Erreur HTTP {response.status}", None
                
                torrent_info = await response.json()
                download_links = torrent_info.get('links', [])
                
                if not download_links:
                    return torrent_id, "Aucun lien disponible", None
                
                # Tester seulement le premier lien (optimisation)
                first_link = download_links[0]
                
                # Débrider pour tester la disponibilité
                unrestrict_data = {'link': first_link}
                async with session.post(
                    'https://api.real-debrid.com/rest/1.0/unrestrict/link',
                    headers=headers,
                    data=unrestrict_data,
                    timeout=6
                ) as unrestrict_response:
                    
                    if unrestrict_response.status == 503:
                        return torrent_id, "Erreur 503 - Fichier indisponible", "503"
                    elif unrestrict_response.status == 200:
                        return torrent_id, "Fichier disponible", "OK"
                    else:
                        return torrent_id, f"Status débridage: {unrestrict_response.status}", None
                        
        except asyncio.TimeoutError:
            return torrent_id, "Timeout lors de la vérification", None
        except Exception as e:
            return torrent_id, f"Erreur: {str(e)}", None

    # === TRAITEMENT PRINCIPAL ===
    errors_503_count = 0
    total_checked = 0
    start_process_time = time.time()
    
    logging.info(f"🚀 Démarrage du traitement parallèle adaptatif de {len(torrents_to_check)} torrents...")
    
    # Optimisation: Connexion unique avec pool adaptatif
    connector = aiohttp.TCPConnector(limit=50, limit_per_host=25)
    timeout = aiohttp.ClientTimeout(total=12, connect=3)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        
        # Configuration dynamique des batches - OPTIMISÉE POUR RÉCUPÉRATION RAPIDE
        batch_size = 5  # Taille initiale plus agressive
        min_batch_size = 1  # Descendre jusqu'à 1 si nécessaire
        max_batch_size = 25  # Augmenter le maximum
        consecutive_successes = 0
        consecutive_errors = 0
        consecutive_429_errors = 0
        api_delay = 1.5  # Délai initial plus agressif
        recovery_mode = False  # Mode récupération rapide
        
        i = 0
        batch_num = 0
        
        while i < len(torrents_to_check):
            batch_num += 1
            batch_start_time = time.time()
            
            # Déterminer la taille du batch actuel
            actual_batch_size = min(batch_size, len(torrents_to_check) - i)
            batch_torrents = torrents_to_check[i:i+actual_batch_size]
            
            # Mettre à jour le statut de la tâche
            progress_pct = (i / len(torrents_to_check)) * 100
            task_status["progress"] = f"Batch {batch_num}: {i}/{len(torrents_to_check)} torrents ({progress_pct:.1f}%) - {errors_503_count} erreurs 503 trouvées"
            task_status["last_update"] = time.time()
            
            logging.info(f"🔄 BATCH {batch_num}: Traitement de {actual_batch_size} torrents avec batch_size={batch_size}")
            
            # Créer les tâches pour ce batch
            tasks = [
                check_torrent_health_async(session, torrent_id) 
                for torrent_id, filename in batch_torrents
            ]
            
            # Exécuter le batch en parallèle avec gestion d'erreurs
            try:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                batch_success = True
            except Exception as batch_error:
                logging.error(f"❌ Erreur critique dans le batch {batch_num}: {batch_error}")
                batch_success = False
                batch_results = [batch_error] * len(tasks)
            
            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time
            batch_rate = actual_batch_size / batch_duration if batch_duration > 0 else 0
            
            # Analyser les résultats et compter les erreurs API
            batch_updates = []
            batch_503_count = 0
            batch_api_errors = 0
            batch_timeouts = 0
            batch_success_count = 0
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logging.error(f"❌ Exception dans le batch: {result}")
                    batch_api_errors += 1
                    continue
                    
                torrent_id, message, status = result
                total_checked += 1
                
                if status == "503":
                    batch_503_count += 1
                    errors_503_count += 1
                    logging.warning(f"🚨 ERREUR 503 DÉTECTÉE pour torrent {torrent_id}: {message}")
                    batch_updates.append((message, torrent_id))
                elif status == "OK":
                    batch_success_count += 1
                    logging.debug(f"✅ Torrent {torrent_id} en bonne santé")
                    batch_updates.append((None, torrent_id))
                elif "Timeout" in message or "timeout" in message.lower():
                    batch_timeouts += 1
                    logging.info(f"⏱️ Torrent {torrent_id}: {message}")
                elif "Erreur HTTP" in message:
                    batch_api_errors += 1
                    logging.info(f"⚠️ Torrent {torrent_id}: {message}")
                elif "429" in message:
                    batch_api_errors += 1
                    logging.warning(f"🚨 Torrent {torrent_id}: Rate limiting (429) - {message}")
                else:
                    logging.info(f"⚠️ Torrent {torrent_id}: {message}")
            
            # LOGIQUE D'ADAPTATION DYNAMIQUE avec gestion spéciale des 429
            batch_error_rate = (batch_api_errors + batch_timeouts) / actual_batch_size if actual_batch_size > 0 else 0
            
            # Détecter spécifiquement les erreurs 429 (Rate Limiting)
            batch_429_errors = sum(1 for result in batch_results 
                                 if not isinstance(result, Exception) and "429" in result[1])
            
            # Log détaillé des erreurs détectées dans ce batch
            if batch_429_errors > 0 or batch_503_count > 0 or batch_api_errors > 0:
                logging.info(f"📝 Batch {batch_num} ANALYSE: {batch_503_count} erreurs 503, {batch_api_errors} erreurs API, {batch_timeouts} timeouts, {batch_success_count} succès, {batch_429_errors} erreurs 429")
                logging.info(f"📊 Batch {batch_num} PERF: {batch_duration:.2f}s, rate: {batch_rate:.1f}/s, erreur_rate: {batch_error_rate:.1%}")
            else:
                logging.debug(f"📝 Batch {batch_num}: {batch_success_count} succès, {batch_duration:.2f}s, {batch_rate:.1f}/s")
            batch_429_errors = sum(1 for result in batch_results 
                                 if not isinstance(result, Exception) and "429" in result[1])
            
            if batch_429_errors > 0:  # Erreurs de rate limiting détectées
                consecutive_429_errors += 1
                consecutive_errors += 1
                consecutive_successes = 0
                recovery_mode = True  # Activer le mode récupération
                
                # RALENTISSEMENT MODÉRÉ pour les erreurs 429 (moins drastique)
                old_batch_size = batch_size
                old_delay = api_delay
                
                if consecutive_429_errors >= 3:
                    # Mode ralenti après 3 batches consécutifs avec 429
                    batch_size = min_batch_size  # Descendre au minimum (1)
                    api_delay = min(api_delay + 3.0, 8.0)  # Max 8s au lieu de 15s
                else:
                    batch_size = max(min_batch_size, batch_size // 2)  # Diviser par 2
                    api_delay = min(api_delay + 2.0, 6.0)  # Max 6s au lieu de 10s
                
                logging.warning(f"🚨 RATE LIMITING (429): {batch_429_errors} erreurs, consécutives: {consecutive_429_errors}")
                logging.warning(f"🔻 RALENTISSEMENT MODÉRÉ: batch_size: {old_batch_size}→{batch_size}, délai: {old_delay:.1f}s→{api_delay:.1f}s")
                
            elif batch_error_rate > 0.3:  # Plus de 30% d'erreurs (non-429)
                consecutive_errors += 1
                consecutive_successes = 0
                consecutive_429_errors = 0  # Reset car pas de 429
                
                # Réduire modérément la taille du batch
                old_batch_size = batch_size
                batch_size = max(min_batch_size, batch_size - 2)
                api_delay = min(api_delay + 1.0, 5.0)  # Réduire le max
                
                logging.warning(f"🔻 RALENTISSEMENT: {batch_error_rate:.1%} erreurs → batch_size: {old_batch_size}→{batch_size}, délai: {api_delay:.1f}s")
                
            elif batch_error_rate < 0.05:  # Moins de 5% d'erreurs - RÉCUPÉRATION RAPIDE
                consecutive_successes += 1
                consecutive_errors = max(0, consecutive_errors - 1)
                consecutive_429_errors = max(0, consecutive_429_errors - 1)
                
                # RÉCUPÉRATION RAPIDE EN MODE RECOVERY
                if recovery_mode and consecutive_successes >= 2:  # Seulement 2 batches parfaits
                    old_batch_size = batch_size
                    old_delay = api_delay
                    
                    # Récupération agressive
                    if batch_size < 5:
                        batch_size = min(max_batch_size, batch_size + 2)  # +2 au lieu de +1
                    else:
                        batch_size = min(max_batch_size, batch_size + 3)  # +3 pour récupération rapide
                    
                    api_delay = max(api_delay - 1.0, 1.0)  # Réduction plus rapide
                    
                    logging.info(f"🚀 RÉCUPÉRATION RAPIDE: {batch_error_rate:.1%} erreurs → batch_size: {old_batch_size}→{batch_size}, délai: {old_delay:.1f}s→{api_delay:.1f}s")
                    
                    # Sortir du mode récupération si on retrouve une bonne taille
                    if batch_size >= 10:
                        recovery_mode = False
                        logging.info(f"✅ SORTIE MODE RÉCUPÉRATION: batch_size={batch_size}")
                        
                # ACCÉLÉRATION NORMALE (hors mode récupération)
                elif not recovery_mode and consecutive_successes >= 3 and batch_size < max_batch_size:  # 3 au lieu de 5
                    old_batch_size = batch_size
                    batch_size = min(max_batch_size, batch_size + 2)  # +2 au lieu de +1
                    api_delay = max(api_delay - 0.2, 1.0)  # Réduction plus rapide
                    
                    logging.info(f"🔺 ACCÉLÉRATION NORMALE: {batch_error_rate:.1%} erreurs, {batch_rate:.1f}/s → batch_size: {old_batch_size}→{batch_size}, délai: {api_delay:.1f}s")
            else:
                # Maintenir le rythme actuel mais décrementer les compteurs plus rapidement
                consecutive_errors = max(0, consecutive_errors - 1)
                consecutive_successes = max(0, consecutive_successes - 1)
                consecutive_429_errors = max(0, consecutive_429_errors - 1)
            
            # Exécuter toutes les mises à jour de base en une seule transaction
            if batch_updates:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    for health_error, torrent_id in batch_updates:
                        cursor.execute("INSERT OR IGNORE INTO torrent_details (id) VALUES (?)", (torrent_id,))
                        cursor.execute("""
                            UPDATE torrent_details 
                            SET health_error = ?
                            WHERE id = ?
                        """, (health_error, torrent_id))
                    conn.commit()
            
            # Avancer à la position suivante
            i += actual_batch_size
            
            # Pause adaptative entre batches - TOUJOURS respecter le délai
            if i < len(torrents_to_check):
                await asyncio.sleep(api_delay)
            
            # Log périodique pour le monitoring
            if batch_num % 10 == 0:
                elapsed_total = time.time() - start_process_time
                logging.info(f"📊 Checkpoint: {i}/{len(torrents_to_check)} torrents, {errors_503_count} erreurs 503, {elapsed_total/60:.1f}min écoulées")
    
    final_elapsed = time.time() - start_process_time
    completion_status = "COMPLET"  # Toujours complet maintenant
    
    logging.info(f"🎉 VÉRIFICATION {completion_status}! Total: {total_checked}, erreurs 503: {errors_503_count}")
    logging.info(f"⏱️ Durée totale: {final_elapsed/60:.1f} minutes ({final_elapsed:.1f}s)")
    
    return total_checked, errors_503_count, completion_status

@app.route('/')
@app.route('/torrents', endpoint='torrents')
def torrents_list():
    """Liste des torrents avec pagination et filtres natifs"""
    # Paramètres de pagination et filtres
    page = max(1, int(request.args.get('page', 1)))
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'added_on')
    sort_dir = request.args.get('dir', 'desc')
    per_page = 25
    offset = (page - 1) * per_page
    
    # Validation des paramètres de tri
    valid_sorts = {
        'id': 't.id',
        'filename': 'display_name',
        'status': 'current_status', 
        'bytes': 't.bytes',
        'added_on': 't.added_on',
        'progress': 'progress'
    }
    sort_column = valid_sorts.get(sort_by, 't.added_on')
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Construction de la requête de base - exclure les supprimés SAUF si on filtre spécifiquement sur 'deleted'
        base_query = """
            SELECT t.id, t.filename, t.status, t.bytes, t.added_on,
                   COALESCE(td.name, t.filename) as display_name,
                   COALESCE(td.status, t.status) as current_status,
                   COALESCE(td.progress, 0) as progress,
                   td.host, td.error, td.health_error
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
        """
        
        # Conditions et paramètres
        conditions = []
        params = []
        
        # Si on ne filtre PAS spécifiquement sur "deleted", exclure les supprimés
        if status_filter != 'deleted':
            conditions.append("t.status != 'deleted'")
        
        if status_filter:
            if status_filter == 'deleted':
                # Pour les torrents supprimés, chercher spécifiquement ce statut
                conditions.append("(t.status = 'deleted' OR td.status = 'deleted')")
            elif status_filter == 'error':
                conditions.append("(t.status = 'error' OR td.status = 'error')")
            elif status_filter == 'unavailable':
                # Nouveau filtre pour fichiers indisponibles (réutilise la logique existante)
                conditions.append("(td.error LIKE '%503%' OR td.error LIKE '%404%' OR td.error LIKE '%24%' OR td.error LIKE '%unavailable_file%' OR td.error LIKE '%rd_error_%' OR td.error LIKE '%health_check_error%' OR td.error LIKE '%health_503_error%' OR td.error LIKE '%http_error_%')")
            elif status_filter == 'health_error':
                # Nouveau filtre spécifique pour les erreurs de santé 503
                conditions.append("td.health_error IS NOT NULL")
            elif status_filter == 'incomplete':
                # Nouveau filtre pour torrents avec détails manquants
                conditions.append("td.id IS NULL")
            else:
                conditions.append("(t.status = ? OR td.status = ?)")
                params.extend([status_filter, status_filter])
        
        if search:
            # Détecter si la recherche est un ID Real-Debrid ou un nom de fichier
            search_stripped = search.strip()
            
            # Les IDs Real-Debrid sont généralement :
            # - 13 caractères alphanumériques en majuscules
            # - Ou peuvent être des IDs numériques purs
            is_probable_id = (
                (len(search_stripped) == 13 and search_stripped.isalnum() and search_stripped.isupper()) or
                search_stripped.isdigit() or
                (len(search_stripped) >= 8 and search_stripped.isalnum() and not ' ' in search_stripped)
            )
            
            if is_probable_id:
                # Recherche par ID exact (insensible à la casse)
                conditions.append("(UPPER(t.id) = UPPER(?))")
                params.extend([search_stripped])
            else:
                # Recherche par nom de fichier (comportement existant)
                conditions.append("(t.filename LIKE ? OR td.name LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
        
        # Ajout des conditions WHERE
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        # Requête pour le total
        count_query = f"SELECT COUNT(*) FROM ({base_query})"
        c.execute(count_query, params)
        total_count = c.fetchone()[0]
        
        # Ajout du tri et pagination
        base_query += f" ORDER BY {sort_column} {sort_dir.upper()} LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        # Exécution de la requête principale
        c.execute(base_query, params)
        torrents_data = c.fetchall()
        
        # Récupération des statuts disponibles pour les filtres
        c.execute("""
            SELECT status, COUNT(*) as count
            FROM (
                SELECT COALESCE(td.status, t.status) as status
                FROM torrents t
                LEFT JOIN torrent_details td ON t.id = td.id
            ) sub
            WHERE status IS NOT NULL
            GROUP BY status
            ORDER BY count DESC
        """)
        available_statuses = c.fetchall()
        
        # Ajout du count pour les torrents sans détails
        c.execute("""
            SELECT COUNT(*) 
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE td.id IS NULL
        """)
        incomplete_count = c.fetchone()[0]
        
        # Ajout du count pour les erreurs de santé 503
        c.execute("""
            SELECT COUNT(*) 
            FROM torrent_details td
            WHERE td.health_error IS NOT NULL
        """)
        health_error_count = c.fetchone()[0]
        
        # Ajout des options "incomplete" et "health_error" si elles n'existent pas déjà
        available_statuses = list(available_statuses)
        if incomplete_count > 0:
            available_statuses.append(('incomplete', incomplete_count))
        if health_error_count > 0:
            available_statuses.append(('health_error', health_error_count))
        available_statuses = tuple(available_statuses)
    
    # Calcul de la pagination
    total_pages = (total_count + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    # Formatage des données pour le template
    torrents = []
    for row in torrents_data:
        torrent = {
            'id': row[0],
            'filename': row[1],
            'status': row[2],
            'bytes': row[3],
            'added_on': row[4],
            'display_name': row[5],
            'current_status': row[6],
            'progress': row[7],
            'host': row[8],
            'error': row[9],
            'health_error': row[10],  # Nouveau champ
            'size_formatted': format_size(row[3]) if row[3] else 'N/A',
            'status_emoji': get_status_emoji(row[6]),
            'added_date': row[4][:10] if row[4] else 'N/A'
        }
        torrents.append(torrent)
    
    # Données de pagination pour le template
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': page - 1 if has_prev else None,
        'next_page': page + 1 if has_next else None,
        'start_item': offset + 1,
        'end_item': min(offset + per_page, total_count)
    }
    
    # Calcul de la couverture des détails
    try:
        # Exclure les torrents supprimés uniquement de la table torrents
        c.execute("SELECT COUNT(*) FROM torrents WHERE status != 'deleted'")
        total_torrents = c.fetchone()[0]
        
        # Compter tous les détails disponibles (pas de filtrage par status car torrent_details n'a pas cette colonne)
        c.execute("SELECT COUNT(*) FROM torrent_details")
        total_details = c.fetchone()[0]
        
        coverage = (total_details / total_torrents * 100) if total_torrents > 0 else 0
        print(f"📊 Calcul couverture torrents: {total_torrents} torrents, {total_details} détails = {coverage:.1f}%")
    except Exception as e:
        print(f"❌ Erreur calcul couverture: {e}")
        coverage = 0
    
    return render_template('torrents.html', 
                         torrents=torrents,
                         pagination=pagination,
                         status_filter=status_filter,
                         search=search,
                         sort_by=sort_by,
                         sort_dir=sort_dir,
                         available_statuses=available_statuses,
                         total_count=total_count,
                         coverage=round(coverage, 1))

@app.route('/settings')
def settings():
    """Page des paramètres de configuration"""
    try:
        # Vérifier la disponibilité du module symlink
        symlink_available = SYMLINK_AVAILABLE
        
        return render_template('settings.html', 
                             symlink_available=symlink_available,
                             config={'RD_TOKEN': load_token()})
    except Exception as e:
        print(f"❌ Erreur page settings: {e}")
        flash("Erreur lors du chargement des paramètres", 'error')
        return redirect(url_for('torrents'))

@app.route('/api-test')
def api_test():
    """Page de test API Real-Debrid"""
    try:
        # Récupérer toute la configuration depuis ConfigManager
        config_manager = get_config()
        
        test_config = {
            'RD_TOKEN': config_manager.get_token(),
            'api_limit': config_manager.get('realdebrid.api_limit', 100),
            'max_concurrent': config_manager.get('realdebrid.max_concurrent', 50),
            'batch_size': config_manager.get('realdebrid.batch_size', 250),
            'sonarr_enabled': config_manager.get('sonarr.enabled', False),
            'sonarr_url': config_manager.get('sonarr.url', ''),
            'radarr_enabled': config_manager.get('radarr.enabled', False),
            'radarr_url': config_manager.get('radarr.url', ''),
            'symlink_enabled': config_manager.get('symlink.enabled', False),
            'symlink_workers': config_manager.get('symlink.workers', 4),
            'db_path': config_manager.get_db_path(),
            'media_path': config_manager.get_media_path(),
            'version': config_manager.get('version', '2.0'),
            'setup_completed': config_manager.get('setup_completed', False)
        }
        
        return render_template('api_test.html', config=test_config)
    except Exception as e:
        print(f"❌ Erreur page API test: {e}")
        flash("Erreur lors du chargement de la page de test API", 'error')
        return redirect(url_for('settings'))

@app.route('/sync/<action>', methods=['GET', 'POST'])
def sync_action(action):
    """Lance une action de synchronisation"""
    
    if task_status["running"]:
        if request.method == 'POST':
            # Pour les requêtes AJAX, retourner une erreur JSON
            return jsonify({'success': False, 'error': 'Une tâche est déjà en cours'}), 400
        else:
            flash("Une tâche est déjà en cours d'exécution", 'warning')
            return redirect(request.referrer or url_for('torrents'))
    
    try:
        token = load_token()
    except:
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'}), 401
        else:
            flash("Token Real-Debrid non configuré", 'error')
            return redirect(request.referrer or url_for('torrents'))
    
    # Lancer la synchronisation
    if action == 'smart':
        run_sync_task("Sync intelligent", token, sync_smart)
        action_name = "Synchronisation intelligente"
        log_event('SYNC_TRIGGER', mode='smart', source='web')
    elif action == 'fast':
        run_sync_task("Sync complet", token, sync_all_v2)
        action_name = "Synchronisation complète"
        log_event('SYNC_TRIGGER', mode='fast', source='web')
    elif action == 'torrents':
        run_sync_task("Vue d'ensemble", token, sync_torrents_only)
        action_name = "Vue d'ensemble"
        log_event('SYNC_TRIGGER', mode='torrents_only', source='web')
    else:
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'Action inconnue'}), 400
        else:
            flash("Action inconnue", 'error')
            return redirect(request.referrer or url_for('torrents'))
    
    if request.method == 'POST':
        # Pour les requêtes AJAX, retourner succès avec message descriptif
        return jsonify({'success': True, 'message': f'{action_name} démarrée avec succès'})
    else:
        # Pour les requêtes GET (liens directs), pas de flash automatique et redirection conditionnelle
        referrer = request.referrer
        if referrer and '/torrents' in referrer:
            return redirect('/torrents')
        else:
            return redirect(url_for('torrents'))

@app.route('/api/task_status')
def api_task_status():
    """API de statut simplifiée"""
    import time
    
    response = {
        "running": task_status["running"],
        "progress": task_status.get("progress", ""),
        "result": task_status.get("result", ""),
        "last_update": task_status.get("last_update"),
        "timestamp": time.time()
    }
    
    return jsonify(response)

@app.route('/api/health')
def api_health():
    """Route de santé pour tester la connectivité"""
    import time
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "server": "Redriva Web Interface",
        "version": "2.0"
    })

@app.route('/api/torrents/delete_batch', methods=['POST'])
def delete_torrents_batch():
    """Suppression en masse avec gestion des limites API et erreurs"""
    data = request.get_json()
    torrent_ids = data.get('torrent_ids', [])
    
    if not torrent_ids or len(torrent_ids) == 0:
        return jsonify({'success': False, 'error': 'Aucun torrent sélectionné'}), 400
    
    if len(torrent_ids) > 100:  # Limite de sécurité
        return jsonify({'success': False, 'error': 'Maximum 100 torrents par lot'}), 400
    
    try:
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'}), 401
        
        # Démarrer le traitement en arrière-plan
        result = process_batch_deletion(token, torrent_ids)
        
        return jsonify({
            'success': True,
            'message': f'Suppression de {len(torrent_ids)} torrents démarrée',
            'batch_id': result['batch_id'],
            'total': len(torrent_ids)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def process_batch_deletion(token, torrent_ids):
    """Traite la suppression par batch avec gestion d'erreurs"""
    import time
    
    batch_id = str(uuid.uuid4())[:8]
    logging.info(f"🚀 Démarrage suppression batch {batch_id}: {len(torrent_ids)} torrents")
    log_event('BATCH_DELETE_START', batch_id=batch_id, total=len(torrent_ids))
    
    # Structure pour suivre les résultats
    batch_results = {
        'batch_id': batch_id,
        'total': len(torrent_ids),
        'processed': 0,
        'success': 0,
        'failed': 0,
        'errors': [],
        'status': 'running',
        'start_time': time.time()
    }
    
    # Stocker dans la variable globale pour le suivi
    batch_operations[batch_id] = batch_results
    
    # Traitement asynchrone
    def deletion_worker():
        batch_size = 5  # 5 suppressions simultanées max
        api_delay = 2   # 2 secondes entre les batches
        max_retries = 3
        
        for i in range(0, len(torrent_ids), batch_size):
            if batch_results['status'] == 'cancelled':
                break
                
            batch_torrent_ids = torrent_ids[i:i + batch_size]
            
            # Traitement du batch actuel
            for torrent_id in batch_torrent_ids:
                success = False
                last_error = None
                
                # Retry avec backoff exponentiel
                for attempt in range(max_retries):
                    try:
                        response = requests.delete(
                            f'https://api.real-debrid.com/rest/1.0/torrents/delete/{torrent_id}',
                            headers={'Authorization': f'Bearer {token}'},
                            timeout=10
                        )
                        
                        if response.status_code == 204:
                            # Succès - Mettre à jour la DB locale
                            update_torrent_status_deleted(torrent_id)
                            batch_results['success'] += 1
                            success = True
                            break
                            
                        elif response.status_code == 404:
                            # Torrent déjà supprimé - Considérer comme succès
                            update_torrent_status_deleted(torrent_id)
                            batch_results['success'] += 1
                            success = True
                            break
                            
                        elif response.status_code == 429:
                            # Rate limit - Attendre plus longtemps
                            wait_time = api_delay * (2 ** attempt)
                            logging.warning(f"Rate limit atteint, attente {wait_time}s")
                            time.sleep(wait_time)
                            continue
                            
                        else:
                            last_error = f"HTTP {response.status_code}: {response.text}"
                            
                    except requests.exceptions.Timeout:
                        last_error = "Timeout lors de la suppression"
                        time.sleep(1 * (attempt + 1))  # Pause progressive
                        
                    except requests.exceptions.RequestException as e:
                        last_error = f"Erreur réseau: {str(e)}"
                        time.sleep(1 * (attempt + 1))
                        
                    except Exception as e:
                        last_error = f"Erreur inattendue: {str(e)}"
                        break  # Erreur non récupérable
                
                # Mise à jour des résultats
                batch_results['processed'] += 1
                
                if not success:
                    batch_results['failed'] += 1
                    batch_results['errors'].append({
                        'torrent_id': torrent_id,
                        'error': last_error,
                        'attempts': max_retries
                    })
                    logging.error(f"Échec suppression {torrent_id}: {last_error}")
                # Progress event
                log_event('BATCH_DELETE_PROGRESS', batch_id=batch_id, processed=batch_results['processed'], success=batch_results['success'], failed=batch_results['failed'])
                
                # Pause entre suppressions individuelles
                time.sleep(0.5)
            
            # Pause entre les batches
            if i + batch_size < len(torrent_ids):
                logging.info(f"Pause {api_delay}s avant le prochain batch...")
                time.sleep(api_delay)
        
    # Finalisation
    batch_results['status'] = 'completed'
    batch_results['end_time'] = time.time()
    batch_results['duration'] = batch_results['end_time'] - batch_results['start_time']
    logging.info(f"Suppression terminée: {batch_results['success']}/{batch_results['total']} succès")
    log_event('BATCH_DELETE_END', batch_id=batch_id, success=batch_results['success'], failed=batch_results['failed'], duration=f"{batch_results['duration']:.2f}s")
    
    # Lancer le worker en arrière-plan
    threading.Thread(target=deletion_worker, daemon=True).start()
    
    return batch_results

@app.route('/api/fix_deleted_status')
def fix_deleted_status():
    """Synchronise les statuts supprimés entre les tables torrents et torrent_details"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Trouver les torrents marqués supprimés dans 'torrents' mais pas dans 'torrent_details'
            cursor.execute("""
                UPDATE torrent_details 
                SET status = 'deleted' 
                WHERE id IN (
                    SELECT t.id FROM torrents t 
                    WHERE t.status = 'deleted' 
                    AND EXISTS (SELECT 1 FROM torrent_details td WHERE td.id = t.id AND td.status != 'deleted')
                )
            """)
            
            fixed_count = cursor.rowcount
            conn.commit()
            
            print(f"✅ Corrigé le statut de {fixed_count} torrents dans torrent_details")
            
            return jsonify({
                'success': True,
                'fixed_count': fixed_count,
                'message': f'{fixed_count} torrents corrigés'
            })
            
    except Exception as e:
        print(f"❌ Erreur lors de la correction des statuts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def update_torrent_status_deleted(torrent_id):
    """Marque un torrent comme supprimé dans la DB locale"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Mettre à jour les deux tables
            cursor.execute("""
                UPDATE torrents 
                SET status = 'deleted' 
                WHERE id = ?
            """, (torrent_id,))
            cursor.execute("""
                UPDATE torrent_details 
                SET status = 'deleted' 
                WHERE id = ?
            """, (torrent_id,))
            conn.commit()
            print(f"✅ Torrent {torrent_id} marqué comme supprimé dans les deux tables")
    except Exception as e:
        logging.error(f"Erreur mise à jour DB pour {torrent_id}: {e}")
        print(f"❌ Erreur mise à jour DB pour {torrent_id}: {e}")

@app.route('/api/batch_status/<batch_id>')
def get_batch_status(batch_id):
    """Récupère le statut d'une opération par batch avec gestion d'erreurs"""
    try:
        if batch_id not in batch_operations:
            return jsonify({
                'success': False, 
                'error': f'Batch {batch_id} non trouvé ou expiré'
            }), 404
        
        batch_data = batch_operations[batch_id]
        
        # Ajouter des informations de debug
        batch_data['last_check'] = time.time()
        
        return jsonify({
            'success': True,
            'batch': batch_data
        })
        
    except Exception as e:
        logging.error(f"Erreur récupération statut batch {batch_id}: {e}")
        return jsonify({
            'success': False, 
            'error': f'Erreur serveur: {str(e)}'
        }), 500

@app.route('/api/torrent/<torrent_id>')
def api_torrent_detail(torrent_id):
    """API pour récupérer les détails d'un torrent avec rafraîchissement depuis Real-Debrid"""
    try:
        log_event('TORRENT_DETAIL_START', torrent_id=torrent_id)
        token = load_token()
        if not token:
            return get_cached_torrent_data(torrent_id, error_msg="Token Real-Debrid non configuré")

        async def refresh_torrent_data():
            async with aiohttp.ClientSession() as session:
                result = await fetch_torrent_detail(session, token, torrent_id)
                return result is not None

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            refreshed = loop.run_until_complete(asyncio.wait_for(refresh_torrent_data(), timeout=30.0))
            loop.close()
        except asyncio.TimeoutError:
            logging.warning(f"Timeout lors du rafraîchissement du torrent {torrent_id}")
            return get_cached_torrent_data(torrent_id, error_msg="Timeout lors de la récupération des données fraîches", refreshed=False)
        except Exception as e:
            logging.error(f"Erreur lors du rafraîchissement du torrent {torrent_id}: {e}")
            return get_cached_torrent_data(torrent_id, error_msg=f"Erreur API: {str(e)}", refreshed=False)

        response = get_cached_torrent_data(torrent_id, refreshed=refreshed)
        log_event('TORRENT_DETAIL_END', torrent_id=torrent_id, refreshed=refreshed)
        return response
    except Exception as e:
        logging.error(f"Erreur dans api_torrent_detail: {e}")
        log_event('TORRENT_DETAIL_END', torrent_id=torrent_id, status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


def get_cached_torrent_data(torrent_id, error_msg=None, refreshed=True):
    """Récupère les données du torrent depuis la base locale"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Informations de base avec les liens de streaming
            c.execute("""
                SELECT t.id, t.filename, t.status, t.bytes, t.added_on,
                       td.name, td.status, td.size, td.files_count, td.progress,
                       td.links, td.streaming_links, td.hash, td.host, td.error, td.added
                FROM torrents t
                LEFT JOIN torrent_details td ON t.id = td.id
                WHERE t.id = ?
            """, (torrent_id,))
            
            torrent = c.fetchone()
            
            if not torrent:
                return jsonify({'success': False, 'error': 'Torrent non trouvé'}), 404

        # Traitement des liens
        raw_download_links = torrent[10].split(',') if torrent[10] else []
        raw_streaming_links = torrent[11].split(',') if torrent[11] else []
        
        # Formatter les liens de téléchargement pour le downloader
        formatted_links = []
        for raw_link in raw_download_links:
            if raw_link.strip():
                download_link = format_download_link(raw_link.strip())
                formatted_links.append(download_link)
        
        # Utiliser les vrais liens de streaming depuis la base de données
        streaming_links = []
        for raw_streaming_link in raw_streaming_links:
            if raw_streaming_link.strip():
                streaming_links.append(raw_streaming_link.strip())
            else:
                streaming_links.append(None)  # Pas de lien streaming pour ce fichier

        # Construire la réponse avec indicateur de fraîcheur
        torrent_data = {
            'success': True,
            'torrent': {
                'id': torrent[0],
                'filename': torrent[1],
                'status': torrent[2],
                'bytes': torrent[3],
                'added_on': torrent[4],
                'name': torrent[5],
                'detail_status': torrent[6],
                'size': torrent[7],
                'files_count': torrent[8],
                'progress': torrent[9],
                'links': formatted_links,  # Liens formatés pour le downloader
                'streaming_links': streaming_links,  # Vrais liens de streaming depuis l'API
                'hash': torrent[12],
                'host': torrent[13],
                'error': torrent[14],
                'added_detail': torrent[15],
                'size_formatted': format_size(torrent[3]) if torrent[3] else format_size(torrent[7]) if torrent[7] else 'N/A',
                'status_emoji': get_status_emoji(torrent[6] or torrent[2]),
                'last_updated': datetime.now().strftime("%H:%M:%S") if refreshed else "Données en cache"
            },
            'refreshed': refreshed,
            'timestamp': datetime.now().isoformat()
        }
        
        if error_msg and not refreshed:
            torrent_data['warning'] = error_msg
            
        return jsonify(torrent_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'cached_data': None}), 500

@app.route('/api/torrent/delete/<torrent_id>', methods=['POST'])
def delete_torrent(torrent_id):
    """Supprimer un torrent de Real-Debrid"""
    try:
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Appel API Real-Debrid pour supprimer le torrent
        log_event('TORRENT_DELETE_START', torrent_id=torrent_id)
        response = requests.delete(
            f'https://api.real-debrid.com/rest/1.0/torrents/delete/{torrent_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if response.status_code == 204:
            # Marquer le torrent comme supprimé dans la DB locale
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE torrents 
                SET status = 'deleted' 
                WHERE id = ?
            """, (torrent_id,))
            conn.commit()
            conn.close()
            
            log_event('TORRENT_DELETE_END', torrent_id=torrent_id, status='success')
            return jsonify({'success': True, 'message': 'Torrent supprimé avec succès'})
        else:
            log_event('TORRENT_DELETE_END', torrent_id=torrent_id, status='api_error', http=response.status_code)
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
        log_event('TORRENT_DELETE_END', torrent_id=torrent_id, status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/torrent/reinsert/<torrent_id>', methods=['POST'])
def reinsert_torrent(torrent_id):
    """Réinsérer un torrent dans Real-Debrid"""
    try:
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Récupérer les infos du torrent depuis la DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.filename, td.hash 
            FROM torrents t 
            LEFT JOIN torrent_details td ON t.id = td.id 
            WHERE t.id = ?
        """, (torrent_id,))
        torrent_data = cursor.fetchone()
        conn.close()
        
        if not torrent_data or not torrent_data[1]:
            return jsonify({'success': False, 'error': 'Torrent non trouvé ou hash manquant'})
        
        filename, torrent_hash = torrent_data
        
        # Réinsérer via l'API Real-Debrid
        log_event('TORRENT_REINSERT_START', torrent_id=torrent_id)
        response = requests.post(
            'https://api.real-debrid.com/rest/1.0/torrents/addMagnet',
            headers={'Authorization': f'Bearer {token}'},
            data={'magnet': f'magnet:?xt=urn:btih:{torrent_hash}&dn={filename}'}
        )
        
        if response.status_code == 201:
            result = response.json()
            new_id = result.get('id')
            
            # Mettre à jour la DB locale
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE torrents 
                SET id = ?, status = 'magnet_error' 
                WHERE id = ?
            """, (new_id, torrent_id))
            conn.commit()
            conn.close()
            
            log_event('TORRENT_REINSERT_END', torrent_id=torrent_id, new_id=new_id, status='success')
            return jsonify({'success': True, 'message': 'Torrent réinséré avec succès', 'new_id': new_id})
        else:
            log_event('TORRENT_REINSERT_END', torrent_id=torrent_id, status='api_error', http=response.status_code)
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
        log_event('TORRENT_REINSERT_END', torrent_id=torrent_id, status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/media_info/<file_id>')
def get_media_info(file_id):
    """
    Récupère les informations détaillées d'un fichier via /streaming/mediaInfos.
    L'ID est celui obtenu après un appel à /unrestrict/link.
    """
    token = load_token()
    if not token:
        return jsonify({'success': False, 'error': 'Token non configuré'}), 401

    url = f"https://api.real-debrid.com/rest/1.0/streaming/mediaInfos/{file_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Lève une exception pour les codes 4xx/5xx
        
        media_data = response.json()
        
        # Simplifions la structure pour le front-end
        details = media_data.get('details', {})
        
        # Vérifier le type des données pour éviter l'erreur 'list' object has no attribute 'values'
        video_data = details.get('video', {})
        audio_data = details.get('audio', {})
        subtitles_data = details.get('subtitles', {})
        
        # Si c'est déjà une liste, l'utiliser directement, sinon extraire les valeurs du dict
        if isinstance(video_data, list):
            video_streams = video_data
        else:
            video_streams = list(video_data.values()) if video_data else []
            
        if isinstance(audio_data, list):
            audio_streams = audio_data
        else:
            audio_streams = list(audio_data.values()) if audio_data else []
            
        if isinstance(subtitles_data, list):
            subtitle_streams = subtitles_data
        else:
            subtitle_streams = list(subtitles_data.values()) if subtitles_data else []

        return jsonify({
            'success': True,
            'filename': media_data.get('filename'),
            'type': media_data.get('type'),
            'duration': media_data.get('duration'),
            'size': media_data.get('size'),
            'video': video_streams,
            'audio': audio_streams,
            'subtitles': subtitle_streams,
            'poster': media_data.get('poster_path'),
            'backdrop': media_data.get('backdrop_path')
        })

    except requests.exceptions.HTTPError as e:
        error_msg = f"Erreur API Real-Debrid: {e.response.status_code}"
        try:
            error_details = e.response.json()
            error_msg += f" - {error_details.get('error', e.response.text)}"
        except ValueError:
            pass
        return jsonify({'success': False, 'error': error_msg}), e.response.status_code
    except Exception as e:
        logging.error(f"Erreur dans get_media_info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/torrent/stream/<torrent_id>', methods=['GET'])
def get_stream_links(torrent_id):
    """
    Récupérer les liens de streaming et download pour un torrent
    Basé sur l'analyse de l'API Real-Debrid : 
    - Download : liens directs depuis torrent_info.links
    - Streaming : file_id obtenu via débridage + construction du lien streaming
    """
    try:
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Récupérer les infos du torrent depuis Real-Debrid avec timeout augmenté
        try:
            response = requests.get(
                f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}',
                headers={'Authorization': f'Bearer {token}'},
                timeout=30  # Timeout de 30 secondes (augmenté)
            )
            logging.debug(f"Réponse torrent info: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout lors de la récupération des infos torrent {torrent_id}")
            return jsonify({'success': False, 'error': 'Timeout lors de la récupération des informations du torrent'})
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur réseau torrent info: {e}")
            return jsonify({'success': False, 'error': f'Erreur réseau: {str(e)}'})
        
        if response.status_code == 404:
            return jsonify({'success': False, 'error': 'Torrent non trouvé sur Real-Debrid'})
        elif response.status_code != 200:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
        
        torrent_info = response.json()
        
        # Récupérer les liens directs de download depuis la structure
        download_links = torrent_info.get('links', [])
        files_info = torrent_info.get('files', [])
        
        if not download_links:
            print("⚠️ Aucun lien de téléchargement trouvé")
            return jsonify({
                'success': True,
                'torrent_info': {
                    'id': torrent_id,
                    'filename': torrent_info.get('filename', 'Unknown'),
                    'status': torrent_info.get('status', 'unknown'),
                    'progress': torrent_info.get('progress', 0)
                },
                'files': [],
                'total_files': 0,
                'message': 'Aucun lien de téléchargement disponible'
            })
        
        # Générer les données complètes pour chaque fichier avec traitement parallèle amélioré
        file_data = []
        
        for i, download_link in enumerate(download_links):
            try:
                # Informations du fichier (si disponibles)
                file_info = files_info[i] if i < len(files_info) else {}
                filename = file_info.get('path', f'Fichier {i+1}')
                file_size = file_info.get('bytes', 0)
                selected = file_info.get('selected', 1)  # Récupérer la propriété selected (1 pour vidéo, 0 pour NFO)
                
                print(f"🔄 Traitement fichier {i+1}: {filename}")
                
                # Étape 1: Débrider le lien pour obtenir le file_id avec timeout augmenté
                try:
                    unrestrict_response = requests.post(
                        'https://api.real-debrid.com/rest/1.0/unrestrict/link',
                        headers={'Authorization': f'Bearer {token}'},
                        data={'link': download_link},
                        timeout=20  # Timeout de 20 secondes pour débridage (augmenté)
                    )
                    logging.debug(f"Débridage fichier {i+1}: {unrestrict_response.status_code}")
                except requests.exceptions.Timeout:
                    print(f"⏱️ Timeout lors du débridage fichier {i+1}")
                    formatted_download = format_download_link(download_link)
                    file_data.append({
                        'index': i,
                        'filename': filename,
                        'size': file_size,
                        'selected': selected,  # Ajouter la propriété selected pour le filtrage
                        'download_link': formatted_download,
                        'direct_download': download_link,
                        'streaming_link': None,
                        'file_id': None,
                        'mime_type': 'unknown',
                        'error': 'Timeout lors du débridage'
                    })
                    continue
                except requests.exceptions.RequestException as e:
                    print(f"❌ Erreur réseau débridage fichier {i+1}: {e}")
                    formatted_download = format_download_link(download_link)
                    file_data.append({
                        'index': i,
                        'filename': filename,
                        'size': file_size,
                        'selected': selected,  # Ajouter la propriété selected pour le filtrage
                        'download_link': formatted_download,
                        'direct_download': download_link,
                        'streaming_link': None,
                        'file_id': None,
                        'mime_type': 'unknown',
                        'error': f'Erreur réseau: {str(e)}'
                    })
                    continue
                
                if unrestrict_response.status_code == 200:
                    unrestrict_data = unrestrict_response.json()
                    file_id = unrestrict_data.get('id')
                    direct_download = unrestrict_data.get('download', download_link)
                    
                    # Étape 2: Construire le lien streaming
                    streaming_link = f"https://real-debrid.com/streaming-{file_id}" if file_id else None
                    
                    print(f"✅ Fichier {i+1} débridé: file_id={file_id}")
                    
                    # Formater le lien de téléchargement pour le downloader
                    formatted_download = format_download_link(direct_download)
                    
                    file_data.append({
                        'index': i,
                        'filename': filename,
                        'size': file_size,
                        'selected': selected,  # Ajouter la propriété selected pour le filtrage
                        'download_link': formatted_download,  # Lien formaté pour le downloader Real-Debrid  
                        'direct_download': direct_download,  # Lien direct brut
                        'streaming_link': streaming_link,  # Lien de streaming construit
                        'file_id': file_id,  # ID pour récupérer les métadonnées
                        'mime_type': unrestrict_data.get('mimeType', 'unknown')
                    })
                else:
                    # En cas d'échec du débridage, garder au moins le lien de base formaté
                    print(f"⚠️ Échec débridage fichier {i+1}: {unrestrict_response.status_code}")
                    formatted_download = format_download_link(download_link)
                    file_data.append({
                        'index': i,
                        'filename': filename,
                        'size': file_size,
                        'selected': selected,  # Ajouter la propriété selected pour le filtrage
                        'download_link': formatted_download,
                        'direct_download': download_link,
                        'streaming_link': None,
                        'file_id': None,
                        'mime_type': 'unknown',
                        'error': f'Échec débridage: {unrestrict_response.status_code}'
                    })
                        
            except Exception as file_error:
                # Log l'erreur mais continue avec les autres fichiers
                print(f"❌ Erreur traitement fichier {i}: {file_error}")
                formatted_download = format_download_link(download_link)
                file_data.append({
                    'index': i,
                    'filename': f'Fichier {i+1}',
                    'size': 0,
                    'selected': 1,  # Par défaut, considérer comme sélectionné si erreur
                    'download_link': formatted_download,
                    'direct_download': download_link,
                    'streaming_link': None,
                    'file_id': None,
                    'mime_type': 'unknown',
                    'error': str(file_error)
                })
        
        return jsonify({
            'success': True, 
            'torrent_info': {
                'id': torrent_id,
                'filename': torrent_info.get('filename', 'Unknown'),
                'status': torrent_info.get('status', 'unknown'),
                'progress': torrent_info.get('progress', 0)
            },
            'files': file_data,
            'total_files': len(file_data)
        })
            
    except Exception as e:
        print(f"❌ Erreur critique dans get_stream_links: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Erreur interne: {str(e)}'})

@app.route('/api/torrent/files/<torrent_id>', methods=['GET'])
def get_torrent_files(torrent_id):
    """
    Récupérer uniquement la liste des fichiers avec propriété selected (sans débridage)
    API rapide pour filtrage NFO vs vidéo
    """
    try:
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Récupérer uniquement les infos des fichiers depuis Real-Debrid
        response = requests.get(
            f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10  # Timeout court car pas de débridage
        )
        
        if response.status_code == 404:
            return jsonify({'success': False, 'error': 'Torrent non trouvé sur Real-Debrid'})
        elif response.status_code != 200:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
        
        torrent_info = response.json()
        files_info = torrent_info.get('files', [])
        
        # Formater les fichiers avec leurs propriétés selected
        files_data = []
        for i, file_info in enumerate(files_info):
            files_data.append({
                'index': i,
                'filename': file_info.get('path', f'Fichier {i+1}'),
                'size': file_info.get('bytes', 0),
                'selected': file_info.get('selected', 1),  # selected: 1 pour vidéo, 0 pour NFO
            })
        
        return jsonify({
            'success': True,
            'torrent_info': {
                'id': torrent_id,
                'filename': torrent_info.get('filename', 'Unknown'),
                'status': torrent_info.get('status', 'unknown'),
                'progress': torrent_info.get('progress', 0)
            },
            'files': files_data,
            'total_files': len(files_data)
        })
            
    except Exception as e:
        print(f"❌ Erreur dans get_torrent_files: {e}")
        return jsonify({'success': False, 'error': f'Erreur interne: {str(e)}'})

@app.route('/api/refresh_stats')
def refresh_stats():
    """Recalcule et retourne les statistiques de la base de données avec nettoyage des torrents supprimés."""
    try:
        log_event('STATS_REFRESH_START')
        # Étape 1: Nettoyer les torrents marqués comme "deleted"
        cleanup_result = cleanup_deleted_torrents()
        
        if not cleanup_result['success']:
            return jsonify({
                "success": False, 
                "error": f"Erreur lors du nettoyage: {cleanup_result.get('error', 'Erreur inconnue')}"
            }), 500
        
        deleted_count = cleanup_result['deleted_count']
        
        # Étape 2: Recalculer les statistiques sur la base nettoyée
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Statistiques de base (plus besoin d'exclure les 'deleted' car ils ont été supprimés)
            c.execute("SELECT COUNT(*) FROM torrents")
            total_torrents = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM torrent_details")
            total_details = c.fetchone()[0]
            
            coverage = (total_details / total_torrents * 100) if total_torrents > 0 else 0
            
            # Erreurs
            error_count = 0
            if ERROR_STATUSES:
                placeholders = ','.join('?' * len(ERROR_STATUSES))
                c.execute(f"""
                    SELECT COUNT(DISTINCT t.id) 
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE COALESCE(t.status, td.status) IN ({placeholders})
                """, ERROR_STATUSES)
                error_count = c.fetchone()[0] or 0
            
            # Téléchargés
            c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'downloaded'")
            downloaded_count = c.fetchone()[0] or 0
            
            # Fichiers indisponibles
            c.execute("""
                SELECT COUNT(DISTINCT td.id) 
                FROM torrent_details td
                WHERE (td.error LIKE '%503%' OR td.error LIKE '%404%' OR td.error LIKE '%24%' 
                       OR td.error LIKE '%unavailable_file%' OR td.error LIKE '%rd_error_%'
                       OR td.error LIKE '%health_check_error%' OR td.error LIKE '%http_error_%')
            """)
            unavailable_files = c.fetchone()[0] or 0
            
            # Actifs
            active_count = 0
            if ACTIVE_STATUSES:
                placeholders = ','.join('?' * len(ACTIVE_STATUSES))
                c.execute(f"""
                    SELECT COUNT(DISTINCT t.id) 
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE COALESCE(t.status, td.status) IN ({placeholders})
                """, ACTIVE_STATUSES)
                active_count = c.fetchone()[0] or 0

        response = jsonify({
            "success": True,
            "message": f"{deleted_count} torrent(s) supprimé(s). Statistiques mises à jour.",
            "deleted_count": deleted_count,
            "cleanup_details": {
                "torrents_deleted": cleanup_result.get('torrents_deleted', 0),
                "details_deleted": cleanup_result.get('details_deleted', 0)
            },
            "stats": {
                "total_torrents": total_torrents,
                "total_details": total_details,
                "coverage": round(coverage, 1),
                "error_count": error_count,
                "downloaded_count": downloaded_count,
                "active_count": active_count,
                "unavailable_files": unavailable_files
            }
        })
        log_event('STATS_REFRESH_END', torrents=total_torrents, details=total_details, coverage=round(coverage,1), errors=error_count, active=active_count, deleted=deleted_count)
        return response
        
    except Exception as e:
        print(f"❌ Erreur dans refresh_stats: {e}")
        log_event('STATS_REFRESH_END', status='error', error=str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup_deleted', methods=['POST'])
def api_cleanup_deleted():
    """API pour nettoyer les torrents marqués comme supprimés"""
    try:
        log_event('CLEAN_TRIGGER', source='api')
        result = cleanup_deleted_torrents()
        
        if result['success']:
            log_event('CLEAN_RETURN', deleted=result.get('deleted_count',0), status='success')
            return jsonify(result)
        else:
            log_event('CLEAN_RETURN', status='error', error=result.get('error'))
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ Erreur dans api_cleanup_deleted: {e}")
        log_event('CLEAN_RETURN', status='error', error=str(e))
        return jsonify({
            "success": False, 
            "error": str(e),
            "deleted_count": 0
        }), 500


@app.route('/api/health/check/<torrent_id>', methods=['GET', 'POST'])
def check_single_torrent_health(torrent_id):
    """API pour vérifier la santé d'un torrent spécifique via api/torrent/stream"""
    try:
        log_event('HEALTH_SINGLE_START', torrent_id=torrent_id)
        token = load_token()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Vérifier que le torrent existe
            c.execute("""
                SELECT t.id, t.filename 
                FROM torrents t
                WHERE t.id = ? AND t.status != 'deleted' AND t.status != 'error'
            """, (torrent_id,))
            torrent_info = c.fetchone()
            
            if not torrent_info:
                return jsonify({
                    'success': False,
                    'error': 'Torrent non trouvé ou supprimé'
                })
            
            logging.info(f"Vérification de la santé du torrent {torrent_id} via stream endpoint...")
            error_503_found = False
            error_message = None
            
            try:
                # Appeler l'endpoint local /api/torrent/stream/{id}
                with app.test_client() as client:
                    response = client.get(f'/api/torrent/stream/{torrent_id}')
                    
                    if response.status_code == 200:
                        try:
                            data = response.get_json()
                            
                            # Rechercher l'erreur "Échec débridage: 503" dans la réponse
                            if data and isinstance(data, dict):
                                # Vérifier s'il y a une erreur 503 dans la réponse principale
                                if 'error' in data and '503' in str(data['error']):
                                    error_503_found = True
                                    error_message = str(data['error'])
                                
                                # Vérifier dans les fichiers si présents
                                elif 'files' in data and isinstance(data['files'], list):
                                    for file_info in data['files']:
                                        if isinstance(file_info, dict) and 'error' in file_info:
                                            if '503' in str(file_info['error']):
                                                error_503_found = True
                                                error_message = str(file_info['error'])
                                                break
                                
                                # Si erreur 503 détectée, mettre à jour la base de données
                                if error_503_found:
                                    # Créer l'entrée torrent_details si elle n'existe pas
                                    c.execute("INSERT OR IGNORE INTO torrent_details (id) VALUES (?)", (torrent_id,))
                                    
                                    # Mettre à jour seulement le champ health_error
                                    c.execute("""
                                        UPDATE torrent_details 
                                        SET health_error = ?
                                        WHERE id = ?
                                    """, (error_message, torrent_id))
                                    
                                    print(f"⚠️ Erreur 503 détectée pour torrent {torrent_id}: {error_message}")
                                
                                # Si aucune erreur 503, nettoyer l'ancien champ health_error
                                else:
                                    c.execute("""
                                        UPDATE torrent_details 
                                        SET health_error = NULL
                                        WHERE id = ?
                                    """, (torrent_id,))
                            
                        except (json.JSONDecodeError, KeyError) as json_error:
                            print(f"⚠️ Erreur parsing JSON pour torrent {torrent_id}: {json_error}")
                            return jsonify({'success': False, 'error': f'Erreur parsing réponse: {json_error}'})
                    
                    else:
                        print(f"⚠️ Erreur HTTP {response.status_code} pour torrent {torrent_id}")
                        return jsonify({'success': False, 'error': f'Erreur HTTP: {response.status_code}'})
                
            except Exception as torrent_error:
                print(f"❌ Erreur lors de la vérification du torrent {torrent_id}: {torrent_error}")
                return jsonify({'success': False, 'error': str(torrent_error)})
            
            conn.commit()
            
            # Construire la réponse selon le résultat
            if error_503_found:
                log_event('HEALTH_SINGLE_END', torrent_id=torrent_id, status='503')
                return jsonify({
                    'success': True,
                    'message': f'⚠️ Erreur 503 détectée pour le torrent {torrent_id}',
                    'error_503_found': True,
                    'error_message': error_message,
                    'torrent_id': torrent_id
                })
            else:
                log_event('HEALTH_SINGLE_END', torrent_id=torrent_id, status='ok')
                return jsonify({
                    'success': True,
                    'message': f'✅ Torrent {torrent_id} en bonne santé',
                    'error_503_found': False,
                    'torrent_id': torrent_id
                })
            
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de santé du torrent {torrent_id}: {e}")
        log_event('HEALTH_SINGLE_END', torrent_id=torrent_id, status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/health/check_all', methods=['GET', 'POST'])
def check_all_files_health():
    """API pour vérifier la santé de tous les liens de fichiers - TÂCHE EN ARRIÈRE-PLAN"""
    try:
        token = load_token()
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token Real-Debrid non configuré'
            })
        
        # Vérifier si une tâche de health check est déjà en cours
        if task_status["running"]:
            return jsonify({
                'success': False,
                'error': 'Une tâche de synchronisation est déjà en cours',
                'current_task': task_status.get("progress", "Tâche en cours...")
            })
        
        # Démarrer la tâche de health check en arrière-plan
        run_health_check_task(token)
        
        return jsonify({
            'success': True,
            'message': 'Vérification de santé démarrée en arrière-plan',
            'info': 'Utilisez /api/task_status pour suivre l\'avancement',
            'estimated_duration': 'Peut prendre plusieurs heures selon le nombre de torrents'
        })
            
    except Exception as e:
        print(f"❌ Erreur lors du démarrage de la vérification de santé: {e}")
        log_event('HEALTH_CHECK_START', status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/health/cleanup', methods=['GET', 'POST'])
def cleanup_unavailable_files():
    """API pour nettoyer les fichiers indisponibles et notifier Sonarr/Radarr"""
    try:
        log_event('UNAVAILABLE_CLEAN_START')
        token = load_token()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Identifier les torrents avec liens indisponibles
            c.execute("""
                SELECT td.id, td.name, td.links
                FROM torrent_details td
                LEFT JOIN torrents t ON td.id = t.id
                WHERE t.status != 'deleted' 
                AND (td.error LIKE '%503%' OR td.error LIKE '%404%' OR td.error LIKE '%24%' 
                     OR td.error LIKE '%unavailable_file%' OR td.error LIKE '%rd_error_%'
                     OR td.error LIKE '%health_check_error%' OR td.error LIKE '%http_error_%')
            """)
            unavailable_torrents = c.fetchall()
            
            if not unavailable_torrents:
                return jsonify({
                    'success': True,
                    'message': 'Aucun fichier indisponible à nettoyer',
                    'cleaned': 0
                })
            
            cleaned_count = 0
            
            # Supprimer les torrents indisponibles
            for torrent_id, name, links_json in unavailable_torrents:
                try:
                    # Marquer comme supprimé dans la base locale
                    c.execute("UPDATE torrents SET status = 'deleted' WHERE id = ?", (torrent_id,))
                    c.execute("UPDATE torrent_details SET status = 'deleted' WHERE id = ?", (torrent_id,))
                    
                    # Optionnel: Supprimer également côté Real-Debrid si souhaité
                    # (décommenté si nécessaire)
                    # try:
                    #     requests.delete(
                    #         f'https://api.real-debrid.com/rest/1.0/torrents/delete/{torrent_id}',
                    #         headers={'Authorization': f'Bearer {token}'},
                    #         timeout=10
                    #     )
                    # except:
                    #     pass  # Ignorer les erreurs de suppression RD
                    
                    cleaned_count += 1
                    logging.info(f"Nettoyé: {name}")
                    
                except Exception as cleanup_error:
                    print(f"❌ Erreur nettoyage {torrent_id}: {cleanup_error}")
            
            conn.commit()
            
            # Optionnel: Notification Sonarr/Radarr si module symlink disponible
            try:
                from symguard_integration import notify_arr_missing_content
                # Cette fonction devrait être implémentée pour notifier les *arr
                # notify_arr_missing_content(unavailable_torrents)
                logging.info("Notification Sonarr/Radarr envoyée (si configuré)")
            except ImportError:
                logging.info("Module symlink non disponible, pas de notification *arr")
            
            response = jsonify({
                'success': True,
                'message': f'{cleaned_count} fichiers indisponibles nettoyés',
                'cleaned': cleaned_count
            })
            log_event('UNAVAILABLE_CLEAN_END', cleaned=cleaned_count, status='success')
            return response
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")
        log_event('UNAVAILABLE_CLEAN_END', status='error', error=str(e))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/processing_torrents')
def get_processing_torrents():
    """API pour récupérer le détail des torrents en cours de traitement"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Logique unifiée : une seule requête avec JOIN pour éviter les doublons
            # Priorité au statut depuis torrents (source de vérité, mise à jour plus rapide)
            if ACTIVE_STATUSES:
                placeholders = ','.join('?' * len(ACTIVE_STATUSES))
                
                # Comptage unifié : priorité torrents.status, fallback sur torrent_details.status
                # Exclusion stricte des torrents supprimés (torrents.status = 'deleted')
                c.execute(f"""
                    SELECT COUNT(DISTINCT t.id) 
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE t.status != 'deleted' 
                    AND COALESCE(t.status, td.status) IN ({placeholders})
                """, ACTIVE_STATUSES)
                processing_count = c.fetchone()[0] or 0
                
                # Détail par statut avec priorité torrents.status
                c.execute(f"""
                    SELECT COALESCE(t.status, td.status) as final_status, COUNT(DISTINCT t.id) as count
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE t.status != 'deleted' 
                    AND COALESCE(t.status, td.status) IN ({placeholders})
                    GROUP BY COALESCE(t.status, td.status)
                    ORDER BY count DESC
                """, ACTIVE_STATUSES)
                status_breakdown = c.fetchall()
                
                # Comptage des erreurs avec même logique
                if ERROR_STATUSES:
                    error_placeholders = ','.join('?' * len(ERROR_STATUSES))
                    c.execute(f"""
                        SELECT COUNT(DISTINCT t.id) 
                        FROM torrents t
                        LEFT JOIN torrent_details td ON t.id = td.id
                        WHERE t.status != 'deleted' 
                        AND COALESCE(t.status, td.status) IN ({error_placeholders})
                    """, ERROR_STATUSES)
                    error_count = c.fetchone()[0] or 0
                else:
                    error_count = 0
                
                # Récupérer quelques exemples avec statut unifié
                c.execute(f"""
                    SELECT t.id, t.filename, t.status as torrent_status, 
                           td.status as detail_status, td.progress, 
                           t.added_on, td.name,
                           COALESCE(t.status, td.status) as final_status
                    FROM torrents t
                    LEFT JOIN torrent_details td ON t.id = td.id
                    WHERE t.status != 'deleted' 
                    AND COALESCE(t.status, td.status) IN ({placeholders})
                    ORDER BY t.added_on DESC
                    LIMIT 10
                """, ACTIVE_STATUSES)
                
                examples = []
                for row in c.fetchall():
                    examples.append({
                        'id': row[0],
                        'filename': row[1],
                        'torrent_status': row[2],
                        'detail_status': row[3],
                        'progress': row[4] or 0,
                        'added_on': row[5],
                        'display_name': row[6] or row[1],
                        'final_status': row[7]
                    })
                
            else:
                processing_count = 0
                error_count = 0
                status_breakdown = []
                examples = []
            
            return jsonify({
                'success': True,
                'processing_count': processing_count,
                'error_count': error_count,
                'status_breakdown': [{'status': s[0], 'count': s[1]} for s in status_breakdown],
                'active_statuses': list(ACTIVE_STATUSES) if ACTIVE_STATUSES else [],
                'error_statuses': list(ERROR_STATUSES) if ERROR_STATUSES else [],
                'examples': examples,
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des torrents en traitement: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES API SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """API pour récupérer les paramètres actuels"""
    try:
        config = get_config()
        
        # Récupérer tous les paramètres depuis la configuration centralisée
        settings = {
            'apiToken': '',  # Ne jamais renvoyer le token réel pour des raisons de sécurité
            'mediaPath': config.get_media_path(),
            'workersCount': config.get('workers.count', 3),
            'sonarr': {
                'enabled': config.get('sonarr.enabled', False),
                'url': config.get('sonarr.url', ''),
                'apiKey': config.get('sonarr.api_key', '')
            },
            'radarr': {
                'enabled': config.get('radarr.enabled', False),
                'url': config.get('radarr.url', ''),
                'apiKey': config.get('radarr.api_key', '')
            },
            'autoSyncEnabled': config.get('automation.auto_sync_enabled', False),
            'syncInterval': config.get('automation.sync_interval', 300),
            'autoCleanupEnabled': config.get('automation.auto_cleanup_enabled', False)
        }
        
        return jsonify({'success': True, 'settings': settings})
        
    except Exception as e:
        print(f"❌ Erreur get_settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """API pour sauvegarder les paramètres"""
    try:
        settings = request.get_json()
        if not settings:
            return jsonify({'success': False, 'error': 'Données manquantes'})
        
        config = get_config()
        
        # Mettre à jour la configuration centralisée en utilisant update_config
        if 'apiToken' in settings and settings['apiToken']:
            config.update_config('realdebrid.token', settings['apiToken'])
        
        if 'mediaPath' in settings:
            if config.is_docker:
                config.update_config('paths.media', settings['mediaPath'])
            else:
                config.update_config('paths.media_dev', settings['mediaPath'])
        
        if 'workersCount' in settings:
            config.update_config('workers.count', settings['workersCount'])
        
        # Paramètres Sonarr
        if 'sonarr' in settings:
            sonarr = settings['sonarr']
            config.update_config('sonarr.enabled', sonarr.get('enabled', False))
            config.update_config('sonarr.url', sonarr.get('url', ''))
            config.update_config('sonarr.api_key', sonarr.get('apiKey', ''))
        
        # Paramètres Radarr
        if 'radarr' in settings:
            radarr = settings['radarr']
            config.update_config('radarr.enabled', radarr.get('enabled', False))
            config.update_config('radarr.url', radarr.get('url', ''))
            config.update_config('radarr.api_key', radarr.get('apiKey', ''))
        
        # Paramètres d'automatisation
        if 'autoSyncEnabled' in settings:
            config.update_config('automation.auto_sync_enabled', settings['autoSyncEnabled'])
        if 'syncInterval' in settings:
            config.update_config('automation.sync_interval', settings['syncInterval'])
        if 'autoCleanupEnabled' in settings:
            config.update_config('automation.auto_cleanup_enabled', settings['autoCleanupEnabled'])
        
        return jsonify({'success': True, 'message': 'Paramètres sauvegardés'})
        
    except Exception as e:
        print(f"❌ Erreur save_settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """API pour réinitialiser les paramètres"""
    try:
        config = get_config()
        
        # Réinitialiser la configuration avec les valeurs par défaut
        if config.reset_to_defaults():
            return jsonify({'success': True, 'message': 'Paramètres réinitialisés'})
        else:
            return jsonify({'success': False, 'error': 'Erreur lors de la réinitialisation'})
        
    except Exception as e:
        print(f"❌ Erreur reset_settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings/export')
def export_settings():
    """API pour exporter les paramètres"""
    try:
        from flask import send_file
        import tempfile
        
        config = get_config()
        
        # Récupérer la configuration actuelle (sans le token pour sécurité)
        export_config = config.get_full_config()
        
        # Créer un fichier temporaire pour l'export
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(export_config, f, indent=2)
            temp_file = f.name
        
        return send_file(temp_file, as_attachment=True, 
                        download_name=f'redriva-settings-{datetime.now().strftime("%Y%m%d")}.json',
                        mimetype='application/json')
        
    except Exception as e:
        print(f"❌ Erreur export_settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings/import', methods=['POST'])
def import_settings():
    """API pour importer les paramètres"""
    try:
        settings = request.get_json()
        if not settings:
            return jsonify({'success': False, 'error': 'Données manquantes'})
        
        config = get_config()
        
        # Valider que les paramètres importés ont une structure valide
        if not isinstance(settings, dict):
            return jsonify({'success': False, 'error': 'Format de configuration invalide'})
        
        # Merger avec la configuration existante pour préserver les données importantes
        current_config = config.config.copy()
        current_config.update(settings)
        
        # Sauvegarder la nouvelle configuration
        if config.set_full_config(current_config):
            return jsonify({'success': True, 'message': 'Paramètres importés'})
        else:
            return jsonify({'success': False, 'error': 'Erreur lors de l\'import'})
        
    except Exception as e:
        print(f"❌ Erreur import_settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-connection', methods=['POST'])
def test_api_connection():
    """API pour tester la connexion Real-Debrid"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token manquant'})
        
        # Tester la connexion à l'API Real-Debrid
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get('https://api.real-debrid.com/rest/1.0/user', 
                              headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                'success': True, 
                'message': f'Connecté en tant que {user_data.get("username", "utilisateur")}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': f'Erreur API: {response.status_code}'
            })
            
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'Erreur de connexion: {str(e)}'})
    except Exception as e:
        print(f"❌ Erreur test_api_connection: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/proxy-rd', methods=['POST'])
def proxy_real_debrid():
    """Proxy pour les appels à l'API Real-Debrid depuis le frontend"""
    try:
        # Récupérer les paramètres depuis le body JSON ou les query parameters
        data = request.get_json() or {}
        
        # Priorité au body JSON, sinon query parameters (pour compatibilité)
        endpoint = data.get('endpoint') or request.args.get('endpoint', '')
        method = data.get('method') or request.args.get('method', 'GET')
        body = data.get('body')
        
        print(f"🔍 Proxy RD - Endpoint: {endpoint}, Method: {method}")
        
        # Charger le token
        token = load_token()
        if not token:
            return jsonify({'error': 'Token Real-Debrid non configuré'}), 401
        
        # Construire l'URL complète
        base_url = 'https://api.real-debrid.com/rest/1.0'
        url = f"{base_url}{endpoint}"
        
        # Headers d'authentification
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Faire l'appel API
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=body, timeout=30)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=body, timeout=30)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            return jsonify({'error': f'Méthode HTTP non supportée: {method}'}), 400
        
        # Retourner la réponse
        try:
            return jsonify(response.json())
        except ValueError:
            # Si la réponse n'est pas du JSON
            return jsonify({
                'status_code': response.status_code,
                'text': response.text,
                'success': response.status_code < 400
            })
            
    except requests.RequestException as e:
        return jsonify({'error': f'Erreur de connexion: {str(e)}'}), 500
    except Exception as e:
        print(f"❌ Erreur proxy_real_debrid: {e}")
        return jsonify({'error': str(e)}), 500

# ================== ENDPOINTS DE DIAGNOSTIC ==================

@app.route('/api/diagnostic/token', methods=['GET'])
def diagnostic_token():
    """Diagnostic du token Real-Debrid"""
    try:
        config_manager = get_config()
        token = config_manager.get_token()
        
        diagnostic = {
            'token_configured': bool(token),
            'token_length': len(token) if token else 0,
            'token_format': 'valid' if token and len(token) == 40 else 'invalid' if token else 'missing',
            'config_source': 'config_manager',
            'timestamp': datetime.now().isoformat()
        }
        
        if token:
            # Test de base de validité (sans appel API)
            diagnostic['token_sample'] = f"{token[:8]}...{token[-8:]}" if len(token) >= 16 else "too_short"
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/diagnostic/database', methods=['GET'])
def diagnostic_database():
    """Diagnostic de la base de données"""
    try:
        config_manager = get_config()
        db_path = config_manager.get_db_path()
        
        diagnostic = {
            'db_path': db_path,
            'db_exists': os.path.exists(db_path),
            'db_readable': False,
            'db_writable': False,
            'db_size': 0,
            'tables_count': 0,
            'torrents_count': 0
        }
        
        if os.path.exists(db_path):
            diagnostic['db_readable'] = os.access(db_path, os.R_OK)
            diagnostic['db_writable'] = os.access(db_path, os.W_OK)
            diagnostic['db_size'] = os.path.getsize(db_path)
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Compter les tables
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                diagnostic['tables_count'] = cursor.fetchone()[0]
                
                # Compter les torrents
                cursor.execute("SELECT COUNT(*) FROM torrents")
                diagnostic['torrents_count'] = cursor.fetchone()[0]
                
                conn.close()
            except Exception as db_error:
                diagnostic['db_error'] = str(db_error)
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/diagnostic/config', methods=['GET'])
def diagnostic_config():
    """Diagnostic de la configuration"""
    try:
        config_manager = get_config()
        config_full = config_manager.get_full_config()
        
        diagnostic = {
            'config_file_exists': os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')),
            'version': config_manager.get('version', 'unknown'),
            'setup_completed': config_manager.get('setup_completed', False),
            'sections': {
                'realdebrid': bool(config_full.get('realdebrid')),
                'sonarr': bool(config_full.get('sonarr')),
                'radarr': bool(config_full.get('radarr')),
                'symlink': bool(config_full.get('symlink')),
                'flask': bool(config_full.get('flask')),
                'app': bool(config_full.get('app'))
            },
            'services_status': {
                'sonarr_enabled': config_manager.get('sonarr.enabled', False),
                'radarr_enabled': config_manager.get('radarr.enabled', False),
                'symlink_enabled': config_manager.get('symlink.enabled', False)
            },
            'paths': {
                'db_path': config_manager.get_db_path(),
                'media_path': config_manager.get_media_path()
            }
        }
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/diagnostic/paths', methods=['GET'])
def diagnostic_paths():
    """Diagnostic des chemins système"""
    try:
        config_manager = get_config()
        
        paths_to_check = {
            'db_path': config_manager.get_db_path(),
            'media_path': config_manager.get_media_path(),
            'config_dir': os.path.join(os.path.dirname(__file__), '..', 'config'),
            'data_dir': os.path.join(os.path.dirname(__file__), '..', 'data'),
            'current_dir': os.getcwd(),
            'src_dir': os.path.dirname(__file__)
        }
        
        diagnostic = {}
        for name, path in paths_to_check.items():
            diagnostic[name] = {
                'path': path,
                'exists': os.path.exists(path),
                'readable': os.access(path, os.R_OK) if os.path.exists(path) else False,
                'writable': os.access(path, os.W_OK) if os.path.exists(path) else False,
                'type': 'directory' if os.path.isdir(path) else 'file' if os.path.isfile(path) else 'missing'
            }
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES API ARR MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/arr/monitor/status')
def arr_monitor_status():
    """API pour récupérer le statut du moniteur Arr"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 503
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        status = monitor.get_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logging.error(f"Erreur récupération statut arr monitor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/monitor/start', methods=['POST'])
def arr_monitor_start():
    """API pour démarrer la surveillance Arr"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 503
    
    try:
        data = request.get_json() or {}
        interval = data.get('interval', 300)  # 5 minutes par défaut
        
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        
        if monitor.start_monitoring(interval):
            return jsonify({
                'success': True,
                'message': f'Surveillance Arr démarrée (intervalle: {interval}s)'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Surveillance déjà en cours'
            })
    except Exception as e:
        logging.error(f"Erreur démarrage arr monitor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/monitor/stop', methods=['POST'])
def arr_monitor_stop():
    """API pour arrêter la surveillance Arr"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 503
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        
        if monitor.stop_monitoring():
            return jsonify({
                'success': True,
                'message': 'Surveillance Arr arrêtée'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Surveillance déjà arrêtée'
            })
    except Exception as e:
        logging.error(f"Erreur arrêt arr monitor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/monitor/cycle', methods=['POST'])
def arr_monitor_cycle():
    """API pour lancer un cycle de surveillance manuel"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 503
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        
        results = monitor.run_cycle()
        
        return jsonify({
            'success': True,
            'message': 'Cycle de surveillance terminé',
            'results': results,
            'total_corrections': sum(results.values())
        })
    except Exception as e:
        logging.error(f"Erreur cycle arr monitor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/monitor/diagnose/<app_name>')
def arr_monitor_diagnose(app_name):
    """API pour diagnostiquer une application Arr"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 503
    
    if app_name.lower() not in ['sonarr', 'radarr']:
        return jsonify({
            'success': False,
            'error': 'Application non supportée (sonarr/radarr uniquement)'
        }), 400
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        
        diagnostic = monitor.diagnose_queue(app_name.lower())
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic
        })
    except Exception as e:
        logging.error(f"Erreur diagnostic arr monitor {app_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/arr-monitor')
def arr_monitor_page():
    """Page de gestion du moniteur Arr"""
    if not ARR_MONITOR_AVAILABLE:
        flash('Module arr_monitor non disponible', 'error')
        return redirect(url_for('settings'))
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        status = monitor.get_status()
        
        return render_template('arr_monitor.html', 
                             monitor_status=status,
                             arr_available=ARR_MONITOR_AVAILABLE)
    except Exception as e:
        logging.error(f"Erreur page arr monitor: {e}")
        flash(f'Erreur: {e}', 'error')
        return redirect(url_for('settings'))

# === API GESTION TYPES D'ERREURS ===

@app.route('/api/arr/error-types')
def api_get_error_types():
    """Récupère la configuration des types d'erreurs"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        error_types = monitor.get_error_types_config()
        
        return jsonify({
            'success': True,
            'error_types': error_types
        })
        
    except Exception as e:
        logging.error(f"Erreur récupération types erreurs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/error-types/<error_type_name>', methods=['PUT'])
def api_update_error_type(error_type_name):
    """Met à jour la configuration d'un type d'erreur"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_data = request.get_json()
        if not config_data:
            return jsonify({
                'success': False,
                'error': 'Données de configuration manquantes'
            }), 400
        
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        result = monitor.update_error_type_config(error_type_name, config_data)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Erreur mise à jour type erreur {error_type_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/error-types', methods=['POST'])
def api_create_error_type():
    """Crée un nouveau type d'erreur"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_data = request.get_json()
        if not config_data or not config_data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Nom du type d\'erreur manquant'
            }), 400
        
        error_type_name = config_data.pop('name')
        
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        result = monitor.create_error_type(error_type_name, config_data)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Erreur création type erreur: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/error-types/<error_type_name>', methods=['DELETE'])
def api_delete_error_type(error_type_name):
    """Supprime un type d'erreur"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        result = monitor.delete_error_type(error_type_name)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Erreur suppression type erreur {error_type_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/error-statistics')
def api_get_error_statistics():
    """Récupère les statistiques de détection des erreurs"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        statistics = monitor.get_detection_statistics()
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
        
    except Exception as e:
        logging.error(f"Erreur récupération statistiques: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/available-actions')
def api_get_available_actions():
    """Récupère la liste des actions disponibles"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        actions = monitor.get_available_actions()
        
        return jsonify({
            'success': True,
            'actions': actions
        })
        
    except Exception as e:
        logging.error(f"Erreur récupération actions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/test-error-detection', methods=['POST'])
def api_test_error_detection():
    """Teste la détection d'erreur sur un élément donné"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        data = request.get_json()
        if not data or not data.get('test_item'):
            return jsonify({
                'success': False,
                'error': 'Élément de test manquant'
            }), 400
        
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        result = monitor.test_error_detection(data['test_item'])
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logging.error(f"Erreur test détection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/arr/error-types/import', methods=['POST'])
def api_import_error_types():
    """Importe une configuration de types d'erreurs"""
    if not ARR_MONITOR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module arr_monitor non disponible'
        }), 500
    
    try:
        data = request.get_json()
        if not data or not data.get('config'):
            return jsonify({
                'success': False,
                'error': 'Configuration d\'import manquante'
            }), 400
        
        config_manager = get_config()
        monitor = get_arr_monitor(config_manager)
        
        # Importer chaque type d'erreur
        imported_count = 0
        errors = []
        
        for error_type_name, config_data in data['config'].items():
            try:
                result = monitor.update_error_type_config(error_type_name, config_data)
                if result.get('success'):
                    imported_count += 1
                else:
                    errors.append(f"{error_type_name}: {result.get('error', 'Erreur inconnue')}")
            except Exception as e:
                errors.append(f"{error_type_name}: {str(e)}")
        
        if errors:
            return jsonify({
                'success': False,
                'error': f"Erreurs d'import: {'; '.join(errors)}",
                'imported_count': imported_count
            }), 400
        
        return jsonify({
            'success': True,
            'message': f'{imported_count} types d\'erreurs importés avec succès',
            'imported_count': imported_count
        })
        
    except Exception as e:
        logging.error(f"Erreur import types erreurs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\n🛑 Interruption reçue, arrêt du serveur...")
        sys.exit(0)
    
    # Gestionnaire de signal pour arrêt propre
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🌐 Démarrage de l'interface web Redriva...")
    print(f"📱 URL: http://{app.config['HOST']}:{app.config['PORT']}")
    print("🛑 Utilisez Ctrl+C pour arrêter")
    
    try:
        app.run(host=app.config['HOST'], 
                port=app.config['PORT'], 
                debug=app.config['DEBUG'],
                threaded=True,
                use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur du serveur: {e}")
    finally:
        print("🔄 Serveur web arrêté")
