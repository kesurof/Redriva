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
from datetime import datetime
import os
import sys
import json
import queue
import logging
from io import StringIO
import contextlib

# Import des fonctions existantes
sys.path.append(os.path.dirname(__file__))
from main import (
    DB_PATH, load_token, sync_smart, sync_all_v2, sync_torrents_only,
    show_stats, diagnose_errors, get_db_stats, format_size, get_status_emoji,
    create_tables, sync_details_only, ACTIVE_STATUSES, ERROR_STATUSES, COMPLETED_STATUSES
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
app.config['HOST'] = '127.0.0.1'
app.config['PORT'] = 5000
app.config['DEBUG'] = False  # Production mode pour interface stable

# Variables globales pour le système de logs avancé
task_status = {
    "running": False, 
    "progress": "", 
    "result": "", 
    "logs": [],
    "start_time": None,
    "current_action": None
}

# Fichier de persistance des logs
LOGS_FILE = "data/webapp_logs.json"

class LogCapture:
    """Capture les logs et print() des fonctions de synchronisation"""
    def __init__(self):
        self.log_queue = queue.Queue()
        self.captured_logs = []
    
    def capture_print(self, text):
        """Capture les print() du code de synchronisation"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {text}"
        self.captured_logs.append(log_entry)
        task_status["logs"].append(log_entry)
        return text
    
    def capture_log(self, level, message):
        """Capture les logs du module logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.captured_logs.append(log_entry)
        task_status["logs"].append(log_entry)
    
    def get_timestamp(self):
        """Timestamp pour les logs"""
        return datetime.now().strftime("%H:%M:%S")

log_capture = LogCapture()

@contextlib.contextmanager
def capture_output():
    """Context manager pour capturer stdout et stderr"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    # Rediriger vers notre système de capture
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    
    try:
        yield sys.stdout, sys.stderr
    finally:
        # Récupérer le contenu capturé
        stdout_content = sys.stdout.getvalue()
        stderr_content = sys.stderr.getvalue()
        
        # Restaurer les sorties originales
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # Ajouter aux logs
        if stdout_content:
            for line in stdout_content.strip().split('\n'):
                if line.strip():
                    log_capture.capture_print(line.strip())
        
        if stderr_content:
            for line in stderr_content.strip().split('\n'):
                if line.strip():
                    log_capture.capture_log("ERROR", line.strip())

def run_sync_task(task_name, token, task_func, *args):
    """Exécute une tâche de sync en arrière-plan avec capture complète des logs"""
    global task_status
    
    def execute_task():
        task_status["running"] = True
        task_status["progress"] = f"Démarrage de {task_name}..."
        task_status["logs"] = []
        task_status["start_time"] = time.time()
        task_status["current_action"] = task_name
        
        # Log de début
        log_capture.capture_log("INFO", f"🚀 Démarrage de {task_name}")
        
        try:
            # Capturer toutes les sorties de la fonction
            with capture_output():
                if args:
                    result = task_func(token, *args)
                else:
                    result = task_func(token)
            
            # Log de succès
            elapsed = time.time() - task_status["start_time"]
            log_capture.capture_log("SUCCESS", f"✅ {task_name} terminée avec succès en {elapsed:.1f}s")
            
            task_status["result"] = f"✅ {task_name} terminée avec succès"
            task_status["progress"] = "Terminé"
            
        except Exception as e:
            # Log d'erreur
            elapsed = time.time() - task_status["start_time"] 
            log_capture.capture_log("ERROR", f"❌ Erreur lors de {task_name}: {str(e)}")
            
            task_status["result"] = f"❌ Erreur: {str(e)}"
            task_status["progress"] = "Erreur"
        
        finally:
            task_status["running"] = False
            # Sauvegarder les logs
            save_logs_to_file()
    
    # Lancer la tâche en arrière-plan
    thread = threading.Thread(target=execute_task)
    thread.daemon = True
    thread.start()
    
    return thread

def save_logs_to_file():
    """Sauvegarde les logs dans un fichier pour persistance"""
    try:
        os.makedirs(os.path.dirname(LOGS_FILE), exist_ok=True)
        
        # Charger les logs existants
        existing_logs = []
        if os.path.exists(LOGS_FILE):
            try:
                with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)
            except:
                existing_logs = []
        
        # Ajouter les nouveaux logs avec métadonnées
        if task_status.get("logs") and task_status.get("start_time"):
            session_logs = {
                "session_id": task_status.get("start_time", time.time()),
                "action": task_status.get("current_action", "Unknown"),
                "timestamp": datetime.now().isoformat(),
                "logs": task_status.get("logs", []),
                "result": task_status.get("result", ""),
                "duration": time.time() - task_status.get("start_time", time.time()) if task_status.get("start_time") else 0
            }
            
            existing_logs.append(session_logs)
            
            # Garder seulement les 10 dernières sessions
            existing_logs = existing_logs[-10:]
            
            # Sauvegarder
            with open(LOGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, indent=2, ensure_ascii=False)
                
    except Exception as e:
        print(f"Erreur sauvegarde logs: {e}")

def load_logs_from_file():
    """Charge les logs persistants"""
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Erreur chargement logs: {e}")
    return []

@app.route('/')
def dashboard():
    """Page d'accueil avec statistiques générales"""
    try:
        create_tables()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # Statistiques de base
            c.execute("SELECT COUNT(*) FROM torrents")
            total_torrents = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM torrent_details")
            total_details = c.fetchone()[0]
            
            coverage = (total_details / total_torrents * 100) if total_torrents > 0 else 0
            
            # Répartition par statut
            c.execute("""
                SELECT status, COUNT(*) as count 
                FROM torrent_details 
                GROUP BY status 
                ORDER BY count DESC 
                LIMIT 8
            """)
            status_data = c.fetchall()
            
            # Torrents récents
            c.execute("""
                SELECT COUNT(*) FROM torrents 
                WHERE datetime(added_on) >= datetime('now', '-24 hours')
            """)
            recent_24h = c.fetchone()[0] or 0
            
            # Taille totale
            c.execute("SELECT SUM(bytes) FROM torrents WHERE bytes > 0")
            total_size = c.fetchone()[0] or 0
            
            # Erreurs (utilisation des constantes)
            placeholders = ','.join('?' * len(ERROR_STATUSES))
            c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ERROR_STATUSES)
            error_count = c.fetchone()[0] or 0
            
                    # Statistiques complémentaires
        # Récupération de la taille moyenne et des activités récentes
        c.execute("""
            SELECT AVG(CAST(size AS REAL)), 
                   SUM(CASE WHEN datetime(added) > datetime('now', '-7 days') THEN 1 ELSE 0 END)
            FROM torrent_details WHERE size IS NOT NULL AND size != ''
        """)
        result = c.fetchone()
        avg_size = result[0] if result and result[0] else 0
        recent_7d = result[1] if result and result[1] else 0
        
        # Progression moyenne
        c.execute("""
            SELECT AVG(CAST(progress AS REAL))
            FROM torrent_details 
            WHERE progress IS NOT NULL AND progress != '' AND progress != 'N/A'
        """)
        avg_progress_result = c.fetchone()
        avg_progress = avg_progress_result[0] if avg_progress_result and avg_progress_result[0] else 0
        
        # Compte des téléchargés
        c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'downloaded'")
        downloaded_count = c.fetchone()[0] or 0
            # Compte des téléchargements actifs (status in ACTIVE_STATUSES)
        if ACTIVE_STATUSES:
            placeholders = ','.join('?' * len(ACTIVE_STATUSES))
            c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ACTIVE_STATUSES)
            active_count = c.fetchone()[0] or 0
        
        stats = {
            'total_torrents': total_torrents,
            'total_details': total_details,
            'coverage': coverage,
            'recent_24h': recent_24h,
            'recent_7d': recent_7d,
            'total_size': format_size(total_size),
            'avg_size': format_size(avg_size) if avg_size > 0 else "N/A",
            'avg_progress': avg_progress,
            'error_count': error_count,
            'active_count': active_count,
            'downloaded_count': downloaded_count,
            'status_data': status_data
        }
        
        return render_template('dashboard.html', stats=stats, task_status=task_status)
        
    except Exception as e:
        flash(f"Erreur lors du chargement des statistiques: {str(e)}", 'error')
        return render_template('dashboard.html', stats={}, task_status=task_status)

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
        
        # Construction de la requête de base
        base_query = """
            SELECT t.id, t.filename, t.status, t.bytes, t.added_on,
                   COALESCE(td.name, t.filename) as display_name,
                   COALESCE(td.status, t.status) as current_status,
                   COALESCE(td.progress, 0) as progress,
                   td.host, td.error
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE t.status != 'deleted'
        """
        
        # Conditions et paramètres
        conditions = []
        params = []
        
        if status_filter:
            if status_filter == 'error':
                conditions.append("(t.status = 'error' OR td.status = 'error')")
            else:
                conditions.append("(t.status = ? OR td.status = ?)")
                params.extend([status_filter, status_filter])
        
        if search:
            conditions.append("(t.filename LIKE ? OR td.name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        # Ajout des conditions WHERE supplémentaires
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
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
    
    return render_template('torrents.html', 
                         torrents=torrents,
                         pagination=pagination,
                         status_filter=status_filter,
                         search=search,
                         sort_by=sort_by,
                         sort_dir=sort_dir,
                         available_statuses=available_statuses,
                         total_count=total_count)

@app.route('/sync/<action>')
def sync_action(action):
    """Lance une action de synchronisation"""
    
    if task_status["running"]:
        flash("Une tâche est déjà en cours d'exécution", 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        token = load_token()
    except:
        flash("Token Real-Debrid non configuré", 'error')
        return redirect(url_for('dashboard'))
    
    # Utiliser le nouveau système de logs avec run_sync_task
    if action == 'smart':
        run_sync_task("Sync intelligent", token, sync_smart)
    elif action == 'fast':
        run_sync_task("Sync rapide", token, sync_all_v2)
    elif action == 'torrents':
        run_sync_task("Sync torrents", token, sync_torrents_only)
    elif action == 'errors':
        run_sync_task("Retry erreurs", token, sync_details_only, "error")
    else:
        flash("Action inconnue", 'error')
        return redirect(url_for('dashboard'))
    
    flash(f"Synchronisation {action} démarrée", 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/task_status')
def api_task_status():
    """API pour obtenir le statut des tâches (AJAX)"""
    return jsonify(task_status)

@app.route('/api/logs')
def api_logs():
    """API pour récupérer les logs des actions"""
    return jsonify({
        "logs": task_status.get("logs", []),
        "running": task_status["running"],
        "current_action": task_status.get("current_action", ""),
        "progress": task_status.get("progress", "")
    })

@app.route('/api/logs/history')
def api_logs_history():
    """API pour récupérer l'historique des logs"""
    history = load_logs_from_file()
    return jsonify({"history": history})

@app.route('/api/logs', methods=['DELETE'])
def api_clear_logs():
    """API pour effacer les logs courants"""
    global task_status
    task_status["logs"] = []
    return jsonify({"status": "logs cleared"})

@app.route('/api/logs/history', methods=['DELETE'])
def api_clear_logs_history():
    """API pour effacer l'historique des logs"""
    try:
        if os.path.exists(LOGS_FILE):
            os.remove(LOGS_FILE)
        return jsonify({"status": "history cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/torrent/<torrent_id>')
def torrent_detail(torrent_id):
    """Détail d'un torrent spécifique"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Informations de base
        c.execute("""
            SELECT t.id, t.filename, t.status, t.bytes, t.added_on,
                   td.name, td.status, td.size, td.files_count, td.progress,
                   td.links, td.hash, td.host, td.error
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
            WHERE t.id = ?
        """, (torrent_id,))
        
        torrent = c.fetchone()
        
        if not torrent:
            flash("Torrent non trouvé", 'error')
            return redirect(url_for('torrents_list'))
    
    torrent_data = {
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
        'links': torrent[10].split(',') if torrent[10] else [],
        'hash': torrent[11],
        'host': torrent[12],
        'error': torrent[13]
    }
    
    return render_template('torrent_detail.html', 
                         torrent=torrent_data,
                         get_status_emoji=get_status_emoji,
                         format_size=format_size)

@app.route('/api/torrent/delete/<torrent_id>', methods=['POST'])
def delete_torrent(torrent_id):
    """Supprimer un torrent de Real-Debrid"""
    try:
        import requests
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Appel API Real-Debrid pour supprimer le torrent
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
                SET status = 'deleted', updated_at = ? 
                WHERE id = ?
            """, (datetime.now().isoformat(), torrent_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Torrent supprimé avec succès'})
        else:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/torrent/reinsert/<torrent_id>', methods=['POST'])
def reinsert_torrent(torrent_id):
    """Réinsérer un torrent dans Real-Debrid"""
    try:
        import requests
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Récupérer les infos du torrent depuis la DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT filename, hash FROM torrents WHERE id = ?", (torrent_id,))
        torrent_data = cursor.fetchone()
        conn.close()
        
        if not torrent_data:
            return jsonify({'success': False, 'error': 'Torrent non trouvé'})
        
        filename, torrent_hash = torrent_data
        
        # Réinsérer via l'API Real-Debrid
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
                SET id = ?, status = 'magnet_error', updated_at = ? 
                WHERE id = ?
            """, (new_id, datetime.now().isoformat(), torrent_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Torrent réinséré avec succès', 'new_id': new_id})
        else:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/torrent/stream/<torrent_id>', methods=['GET'])
def get_stream_links(torrent_id):
    """Récupérer les liens de streaming pour un torrent"""
    try:
        import requests
        token = load_token()
        if not token:
            return jsonify({'success': False, 'error': 'Token Real-Debrid non configuré'})
        
        # Récupérer les infos du torrent depuis Real-Debrid
        response = requests.get(
            f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if response.status_code == 200:
            torrent_info = response.json()
            
            # Générer les liens de streaming pour les fichiers vidéo
            stream_links = []
            if 'files' in torrent_info:
                for file_info in torrent_info['files']:
                    if file_info.get('selected', 0) == 1:
                        # Obtenir le lien de téléchargement
                        download_response = requests.post(
                            'https://api.real-debrid.com/rest/1.0/unrestrict/link',
                            headers={'Authorization': f'Bearer {token}'},
                            data={'link': file_info['link']}
                        )
                        
                        if download_response.status_code == 200:
                            download_info = download_response.json()
                            stream_links.append({
                                'filename': file_info['path'],
                                'size': file_info['bytes'],
                                'download_link': download_info['download'],
                                'stream_link': download_info['download'].replace('http:', 'https:')
                            })
            
            return jsonify({'success': True, 'links': stream_links})
        else:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
