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

# Import des fonctions existantes
sys.path.append(os.path.dirname(__file__))
from main import (
    DB_PATH, load_token, sync_smart, sync_all_v2, sync_torrents_only,
    show_stats, diagnose_errors, get_db_stats, format_size, get_status_emoji,
    create_tables, sync_details_only
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
app.config['HOST'] = '127.0.0.1'
app.config['PORT'] = 5000
app.config['DEBUG'] = False  # Production mode pour interface stable

# Variable globale pour les tâches en cours
current_task = None
task_status = {"running": False, "progress": "", "result": "", "logs": []}

def run_sync_task(task_name, token, task_func, *args):
    """Exécute une tâche de sync en arrière-plan avec capture des logs"""
    global task_status
    task_status["running"] = True
    task_status["progress"] = f"🔄 {task_name} en cours..."
    task_status["result"] = ""
    task_status["logs"] = [f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Démarrage: {task_name}"]
    
    try:
        # Redirection de la sortie pour capturer les logs
        import io
        import contextlib
        from contextlib import redirect_stdout, redirect_stderr
        
        log_capture = io.StringIO()
        
        with redirect_stdout(log_capture), redirect_stderr(log_capture):
            if asyncio.iscoroutinefunction(task_func):
                result = asyncio.run(task_func(token, *args))
            else:
                result = task_func(token, *args)
        
        # Récupération des logs capturés
        captured_output = log_capture.getvalue()
        if captured_output:
            log_lines = captured_output.strip().split('\n')
            for line in log_lines[-10:]:  # Garder les 10 dernières lignes
                if line.strip():
                    task_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {line.strip()}")
        
        task_status["result"] = f"✅ {task_name} terminé avec succès"
        task_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {task_name} terminé")
        if result:
            task_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Résultat: {result}")
            
    except Exception as e:
        error_msg = str(e)
        task_status["result"] = f"❌ Erreur: {error_msg}"
        task_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erreur: {error_msg}")
    finally:
        task_status["running"] = False
        # Limiter les logs à 50 entrées
        if len(task_status["logs"]) > 50:
            task_status["logs"] = task_status["logs"][-50:]

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
            
            # Erreurs
            c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'error'")
            error_count = c.fetchone()[0] or 0
            
            # Téléchargements actifs
            c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'downloading'")
            downloading_count = c.fetchone()[0] or 0
            
        stats = {
            'total_torrents': total_torrents,
            'total_details': total_details,
            'coverage': coverage,
            'recent_24h': recent_24h,
            'total_size': format_size(total_size),
            'error_count': error_count,
            'downloading_count': downloading_count,
            'status_data': status_data
        }
        
        return render_template('dashboard.html', stats=stats, task_status=task_status)
        
    except Exception as e:
        flash(f"Erreur lors du chargement des statistiques: {str(e)}", 'error')
        return render_template('dashboard.html', stats={}, task_status=task_status)

@app.route('/torrents')
def torrents_list():
    """Liste des torrents avec pagination et filtres"""
    page = int(request.args.get('page', 1))
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    per_page = 50
    offset = (page - 1) * per_page
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Construction de la requête avec filtres
        base_query = """
            SELECT t.id, t.filename, t.status, t.bytes, t.added_on,
                   td.name, td.status as detail_status, td.progress, td.host, td.error
            FROM torrents t
            LEFT JOIN torrent_details td ON t.id = td.id
        """
        
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
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        # Requête pour les données
        query = base_query + " ORDER BY t.added_on DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        c.execute(query, params)
        torrents = c.fetchall()
        
        # Requête pour le total (pagination)
        count_params = params[:-2] if conditions else []
        count_query = f"SELECT COUNT(*) FROM ({base_query})"
        c.execute(count_query, count_params)
        total = c.fetchone()[0]
        
        # Statuts disponibles pour le filtre
        c.execute("""
            SELECT status, COUNT(*) as count 
            FROM (
                SELECT COALESCE(td.status, t.status) as status 
                FROM torrents t 
                LEFT JOIN torrent_details td ON t.id = td.id
            ) 
            WHERE status IS NOT NULL 
            GROUP BY status 
            ORDER BY count DESC
        """)
        available_statuses = c.fetchall()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total
    }
    
    return render_template('torrents.html', 
                         torrents=torrents, 
                         pagination=pagination,
                         status_filter=status_filter,
                         search=search,
                         available_statuses=available_statuses,
                         get_status_emoji=get_status_emoji,
                         format_size=format_size)

@app.route('/sync/<action>')
def sync_action(action):
    """Lance une action de synchronisation"""
    global current_task
    
    if task_status["running"]:
        flash("Une tâche est déjà en cours d'exécution", 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        token = load_token()
    except:
        flash("Token Real-Debrid non configuré", 'error')
        return redirect(url_for('dashboard'))
    
    # Démarrer la tâche en arrière-plan
    if action == 'smart':
        current_task = threading.Thread(target=run_sync_task, 
                                       args=("Sync intelligent", token, sync_smart))
    elif action == 'fast':
        current_task = threading.Thread(target=run_sync_task, 
                                       args=("Sync rapide", token, sync_all_v2))
    elif action == 'torrents':
        current_task = threading.Thread(target=run_sync_task, 
                                       args=("Sync torrents", token, sync_torrents_only))
    elif action == 'errors':
        current_task = threading.Thread(target=run_sync_task, 
                                       args=("Retry erreurs", token, sync_details_only, "error"))
    else:
        flash("Action inconnue", 'error')
        return redirect(url_for('dashboard'))
    
    current_task.daemon = True
    current_task.start()
    
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
        "running": task_status["running"]
    })

@app.route('/api/logs', methods=['DELETE'])
def api_clear_logs():
    """API pour effacer les logs"""
    global task_status
    task_status["logs"] = []
    return jsonify({"status": "logs cleared"})

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
