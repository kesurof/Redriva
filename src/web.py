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

# Import des fonctions existantes
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import (
    DB_PATH, load_token, sync_smart, sync_all_v2, sync_torrents_only,
    show_stats, diagnose_errors, get_db_stats, format_size, get_status_emoji,
    create_tables, sync_details_only, ACTIVE_STATUSES, ERROR_STATUSES, COMPLETED_STATUSES,
    fetch_torrent_detail, upsert_torrent_detail
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
app.config['HOST'] = '127.0.0.1'
app.config['PORT'] = 5000  # Port par défaut
app.config['DEBUG'] = False  # Mode debug temporaire pour diagnostiquer l'erreur 403

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
    return render_template('dashboard.html', 
                         stats={'total_torrents': 0, 'total_details': 0, 'coverage': 0}, 
                         task_status=task_status,
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
    return render_template('dashboard.html', 
                         stats={'total_torrents': 0, 'total_details': 0, 'coverage': 0}, 
                         task_status=task_status,
                         error_500=True), 500

@app.before_request
def log_request_info():
    """Log toutes les requêtes pour diagnostic"""
    print(f"🔍 Requête: {request.method} {request.path}")
    print(f"   Remote addr: {request.remote_addr}")
    print(f"   User agent: {request.headers.get('User-Agent', 'N/A')}")

# Variables globales pour le statut des tâches (améliorées)
task_status = {
    "running": False, 
    "progress": "", 
    "result": "",
    "last_update": None
}

def format_download_link(direct_link):
    """Transforme un lien direct en lien downloader Real-Debrid"""
    if not direct_link or not direct_link.startswith('https://real-debrid.com/d/'):
        return direct_link
    
    # URL encoder le lien complet
    encoded_link = urllib.parse.quote(direct_link, safe='')
    return f"https://real-debrid.com/downloader?links={encoded_link}"

def run_sync_task(task_name, token, task_func, *args):
    """Version simplifiée sans capture d'output"""
    def execute_task():
        import time
        
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
            
        except Exception as e:
            task_status["result"] = f"❌ Erreur dans {task_name}: {str(e)}"
            task_status["running"] = False
            task_status["last_update"] = time.time()
    
    # Lancer la tâche en arrière-plan
    thread = threading.Thread(target=execute_task)
    thread.daemon = True
    thread.start()
    
    return thread

@app.route('/')
def dashboard():
    """Page d'accueil avec statistiques générales et gestion d'erreurs renforcée"""
    try:
        print("🔍 Début de la fonction dashboard()")
        
        # Vérifier le token avant tout
        try:
            token = load_token()
            print(f"✅ Token chargé: {token[:10]}...")
        except Exception as token_error:
            print(f"❌ Erreur token: {token_error}")
            flash("⚠️ Token Real-Debrid non configuré ou invalide", 'warning')
            return render_template('dashboard.html', 
                                 stats={'total_torrents': 0, 'total_details': 0, 'coverage': 0}, 
                                 task_status=task_status,
                                 no_token=True)
        
        create_tables()
        print("✅ Tables créées/vérifiées")
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            try:
                # Statistiques de base
                c.execute("SELECT COUNT(*) FROM torrents")
                total_torrents = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM torrent_details")
                total_details = c.fetchone()[0]
                
                coverage = (total_details / total_torrents * 100) if total_torrents > 0 else 0
                print(f"📊 Stats de base: {total_torrents} torrents, {total_details} détails")
            except sqlite3.Error as db_error:
                print(f"❌ Erreur DB lors des stats de base: {db_error}")
                flash("Erreur d'accès à la base de données", 'error')
                return render_template('dashboard.html', 
                                     stats={'total_torrents': 0, 'total_details': 0, 'coverage': 0}, 
                                     task_status=task_status,
                                     db_error=True)
            
            try:
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
                if ERROR_STATUSES:
                    placeholders = ','.join('?' * len(ERROR_STATUSES))
                    c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ERROR_STATUSES)
                    error_count = c.fetchone()[0] or 0
                else:
                    error_count = 0
                    
                print(f"📊 Stats avancées calculées: {error_count} erreurs")
                
            except sqlite3.Error as db_error:
                print(f"❌ Erreur DB lors des stats avancées: {db_error}")
                # Valeurs par défaut en cas d'erreur
                status_data = []
                recent_24h = 0
                total_size = 0
                error_count = 0
            
            try:
                # Statistiques complémentaires
                # Récupération des activités récentes
                c.execute("""
                    SELECT SUM(CASE WHEN datetime(added) > datetime('now', '-7 days') THEN 1 ELSE 0 END)
                    FROM torrent_details
                """)
                result = c.fetchone()
                recent_7d = result[0] if result and result[0] else 0
                
                
                # Compte des téléchargés
                c.execute("SELECT COUNT(*) FROM torrent_details WHERE status = 'downloaded'")
                downloaded_count = c.fetchone()[0] or 0
                
                # Compte des téléchargements actifs (status in ACTIVE_STATUSES)
                if ACTIVE_STATUSES:
                    placeholders = ','.join('?' * len(ACTIVE_STATUSES))
                    c.execute(f"SELECT COUNT(*) FROM torrent_details WHERE status IN ({placeholders})", ACTIVE_STATUSES)
                    active_count = c.fetchone()[0] or 0
                else:
                    active_count = 0
                    
                print(f"📊 Stats finales calculées: {downloaded_count} téléchargés, {active_count} actifs")
                
            except sqlite3.Error as db_error:
                print(f"❌ Erreur DB lors des stats complémentaires: {db_error}")
                # Valeurs par défaut
                recent_7d = 0
                downloaded_count = 0
                active_count = 0
        
        stats = {
            'total_torrents': total_torrents,
            'total_details': total_details,
            'coverage': coverage,
            'recent_24h': recent_24h,
            'recent_7d': recent_7d,
            'total_size': format_size(total_size),
            'error_count': error_count,
            'active_count': active_count,
            'downloaded_count': downloaded_count,
            'status_data': status_data
        }
        
        print(f"✅ Dashboard chargé avec succès: {len(stats)} statistiques")
        return render_template('dashboard.html', stats=stats, task_status=task_status)
        
    except Exception as e:
        print(f"❌ Erreur critique dans dashboard(): {e}")
        import traceback
        traceback.print_exc()
        
        flash(f"Erreur lors du chargement des statistiques: {str(e)}", 'error')
        return render_template('dashboard.html', 
                             stats={'total_torrents': 0, 'total_details': 0, 'coverage': 0}, 
                             task_status=task_status,
                             critical_error=True)

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
        run_sync_task("Sync complet", token, sync_all_v2)
    elif action == 'torrents':
        run_sync_task("Vue d'ensemble", token, sync_torrents_only)
    else:
        flash("Action inconnue", 'error')
        return redirect(url_for('dashboard'))
    
    flash(f"Synchronisation {action} démarrée", 'success')
    return redirect(url_for('dashboard'))

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

@app.route('/api/debug/status')
def debug_status():
    """Route de debug pour surveiller l'état interne"""
    import time
    return jsonify({
        "task_status": task_status,
        "current_time": time.time(),
        "server_running": True
    })

@app.route('/api/torrent/<torrent_id>')
def api_torrent_detail(torrent_id):
    """API pour récupérer les détails d'un torrent avec rafraîchissement depuis Real-Debrid"""
    try:
        # 1. Charger le token Real-Debrid
        token = load_token()
        if not token:
            # Fallback sur les données en cache si pas de token
            return get_cached_torrent_data(torrent_id, error_msg="Token Real-Debrid non configuré")
        
        # 2. Rafraîchir les données depuis l'API Real-Debrid
        import asyncio
        import aiohttp
        
        async def refresh_torrent_data():
            async with aiohttp.ClientSession() as session:
                result = await fetch_torrent_detail(session, token, torrent_id)
                return result is not None
        
        # 3. Exécuter le rafraîchissement (avec timeout)
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
        
        # 4. Récupérer les données mises à jour depuis la base
        return get_cached_torrent_data(torrent_id, refreshed=refreshed)
        
    except Exception as e:
        logging.error(f"Erreur dans api_torrent_detail: {e}")
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
            return redirect(url_for('torrents'))
    
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
                SET status = 'deleted' 
                WHERE id = ?
            """, (torrent_id,))
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
            
            return jsonify({'success': True, 'message': 'Torrent réinséré avec succès', 'new_id': new_id})
        else:
            return jsonify({'success': False, 'error': f'Erreur API Real-Debrid: {response.status_code}'})
            
    except Exception as e:
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
        
        print(f"🔍 Récupération des liens pour torrent: {torrent_id}")
        
        # Récupérer les infos du torrent depuis Real-Debrid avec timeout augmenté
        try:
            response = requests.get(
                f'https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}',
                headers={'Authorization': f'Bearer {token}'},
                timeout=30  # Timeout de 30 secondes (augmenté)
            )
            print(f"📡 Réponse torrent info: {response.status_code}")
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
        print(f"✅ Torrent info récupéré: {torrent_info.get('filename', 'N/A')}")
        
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
                
                print(f"🔄 Traitement fichier {i+1}: {filename}")
                
                # Étape 1: Débrider le lien pour obtenir le file_id avec timeout augmenté
                try:
                    unrestrict_response = requests.post(
                        'https://api.real-debrid.com/rest/1.0/unrestrict/link',
                        headers={'Authorization': f'Bearer {token}'},
                        data={'link': download_link},
                        timeout=20  # Timeout de 20 secondes pour débridage (augmenté)
                    )
                    print(f"📡 Débridage fichier {i+1}: {unrestrict_response.status_code}")
                except requests.exceptions.Timeout:
                    print(f"⏱️ Timeout lors du débridage fichier {i+1}")
                    formatted_download = format_download_link(download_link)
                    file_data.append({
                        'index': i,
                        'filename': filename,
                        'size': file_size,
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
                    'download_link': formatted_download,
                    'direct_download': download_link,
                    'streaming_link': None,
                    'file_id': None,
                    'mime_type': 'unknown',
                    'error': str(file_error)
                })
        
        print(f"✅ Traitement terminé: {len(file_data)} fichiers traités")
        
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
