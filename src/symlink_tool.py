#!/usr/bin/env python3
"""
Symlink Manager - Module d'intégration pour Redriva
Gestionnaire de liens symboliques avec interface web
"""

import os
import sys
import sqlite3
import threading
import time
import json
import logging
import subprocess
import requests
import uuid
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from flask import request, jsonify, render_template, flash

# Import du gestionnaire de configuration
from config_manager import config_manager, get_config

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales pour la gestion des tâches
active_scans = {}
scan_results = {}

class SymlinkDatabase:
    """Gestionnaire de base de données pour le Symlink Manager"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Utiliser la configuration centralisée pour le chemin de la base
            config = get_config()
            self.db_path = config.get_database_path()
        else:
            self.db_path = db_path
        
        # Créer le répertoire parent si nécessaire
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_tables()
    
    def init_tables(self):
        """Initialise les tables nécessaires"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table de configuration
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS symlink_config (
                        id INTEGER PRIMARY KEY,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Table des scans
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS symlink_scans (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        config TEXT,
                        results TEXT,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT
                    )
                ''')
                
                conn.commit()
                logger.info("✅ Tables symlink initialisées")
                
        except Exception as e:
            logger.error(f"❌ Erreur initialisation tables symlink: {e}")
            raise

    def get_config(self) -> Dict[str, Any]:
        """Récupère la configuration complète depuis le gestionnaire centralisé"""
        try:
            config = get_config()
            return config.get_symlink_config()
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération config: {e}")
            # Configuration par défaut en cas d'erreur
            return {
                'enabled': True,
                'media_path': '/app/medias',
                'workers': 4,
                'sonarr_enabled': False,
                'sonarr_url': 'http://localhost:8989',
                'sonarr_api_key': '',
                'radarr_enabled': False,
                'radarr_url': 'http://localhost:7878',
                'radarr_api_key': ''
            }

    def save_config(self, config_data: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration dans le gestionnaire centralisé"""
        try:
            config = get_config()
            
            # Mettre à jour chaque paramètre
            for key, value in config_data.items():
                config.set(f'symlink.{key}', value)
            
            # Sauvegarder
            config.save()
            
            # Aussi sauvegarder dans la base locale pour compatibilité
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for key, value in config_data.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO symlink_config (key, value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))
                
                conn.commit()
            logger.info("✅ Configuration symlink sauvegardée")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde config: {e}")
            return False

    def save_scan(self, scan_id: str, status: str, config: Dict = None, results: Dict = None, error: str = None):
        """Sauvegarde un scan"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO symlink_scans 
                    (id, status, config, results, started_at, completed_at, error_message)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 
                            CASE WHEN ? IN ('completed', 'error', 'cancelled') THEN CURRENT_TIMESTAMP ELSE NULL END, ?)
                ''', (scan_id, status, json.dumps(config) if config else None, 
                      json.dumps(results) if results else None, status, error))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde scan: {e}")

    def get_recent_scans(self, limit: int = 3) -> List[Dict]:
        """Récupère les scans récents"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, status, config, results, started_at, completed_at, error_message
                    FROM symlink_scans 
                    ORDER BY started_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                scans = []
                for row in cursor.fetchall():
                    scan = {
                        'id': row[0],
                        'status': row[1],
                        'config': json.loads(row[2]) if row[2] else {},
                        'results': json.loads(row[3]) if row[3] else {},
                        'started_at': row[4],
                        'completed_at': row[5],
                        'error_message': row[6]
                    }
                    scans.append(scan)
                
                return scans
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération scans: {e}")
            return []

# Instance globale de la base de données
db = None

class WebSymlinkChecker:
    """Gestionnaire de vérification des symlinks pour l'interface web"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cancelled = False
        
    def scan_directories(self, directories: List[str], mode: str = 'dry-run', 
                        depth: str = 'basic', progress_callback=None) -> Dict[str, Any]:
        """Lance un scan des répertoires sélectionnés"""
        results = {
            'status': 'running',
            'progress': 0,
            'total_dirs': len(directories),
            'processed_dirs': 0,
            'found_issues': 0,
            'directories': {},
            'summary': {}
        }
        
        try:
            for i, directory in enumerate(directories):
                if self.cancelled:
                    results['status'] = 'cancelled'
                    break
                    
                if progress_callback:
                    progress_callback(f"Scan du répertoire {i+1}/{len(directories)}: {directory}")
                
                # Simulation du scan (à remplacer par la vraie logique)
                time.sleep(1)  # Simulation du travail
                
                dir_results = self._scan_single_directory(directory, mode, depth)
                results['directories'][directory] = dir_results
                results['processed_dirs'] += 1
                results['found_issues'] += dir_results.get('issues_count', 0)
                results['progress'] = int((i + 1) / len(directories) * 100)
            
            if not self.cancelled:
                results['status'] = 'completed'
                results['summary'] = self._generate_summary(results['directories'])
            
        except Exception as e:
            logger.error(f"❌ Erreur pendant le scan: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results
    
    def _scan_single_directory(self, directory: str, mode: str, depth: str) -> Dict[str, Any]:
        """Scan d'un répertoire individuel"""
        result = {
            'path': directory,
            'status': 'scanned',
            'files_count': 0,
            'symlinks_count': 0,
            'broken_symlinks': [],
            'issues_count': 0
        }
        
        try:
            if not os.path.exists(directory):
                result['status'] = 'not_found'
                result['issues_count'] = 1
                return result
            
            # Compter les fichiers et symlinks
            for root, dirs, files in os.walk(directory):
                if self.cancelled:
                    break
                    
                for file in files:
                    file_path = os.path.join(root, file)
                    result['files_count'] += 1
                    
                    if os.path.islink(file_path):
                        result['symlinks_count'] += 1
                        if not os.path.exists(file_path):
                            result['broken_symlinks'].append(file_path)
                            result['issues_count'] += 1
            
        except Exception as e:
            logger.error(f"❌ Erreur scan répertoire {directory}: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _generate_summary(self, directories: Dict[str, Any]) -> Dict[str, Any]:
        """Génère un résumé des résultats"""
        summary = {
            'total_files': 0,
            'total_symlinks': 0,
            'total_broken': 0,
            'directories_scanned': len(directories),
            'directories_with_issues': 0
        }
        
        for dir_data in directories.values():
            summary['total_files'] += dir_data.get('files_count', 0)
            summary['total_symlinks'] += dir_data.get('symlinks_count', 0)
            summary['total_broken'] += len(dir_data.get('broken_symlinks', []))
            
            if dir_data.get('issues_count', 0) > 0:
                summary['directories_with_issues'] += 1
        
        return summary
    
    def cancel(self):
        """Annule le scan en cours"""
        self.cancelled = True

class SymlinkTaskManager:
    """Gestionnaire des tâches asynchrones pour les scans"""
    
    def __init__(self):
        self.active_tasks = {}
        self.task_results = {}
    
    def start_scan(self, scan_id: str, config: Dict[str, Any]) -> bool:
        """Démarre un scan en arrière-plan"""
        if scan_id in self.active_tasks:
            return False
        
        def scan_worker():
            try:
                db.save_scan(scan_id, 'running', config)
                
                checker = WebSymlinkChecker(config)
                self.active_tasks[scan_id] = checker
                
                def progress_callback(message):
                    # Mise à jour du progrès
                    pass
                
                directories = config.get('directories', [])
                mode = config.get('mode', 'dry-run')
                depth = config.get('depth', 'basic')
                
                results = checker.scan_directories(directories, mode, depth, progress_callback)
                
                if results['status'] == 'completed':
                    db.save_scan(scan_id, 'completed', config, results)
                elif results['status'] == 'cancelled':
                    db.save_scan(scan_id, 'cancelled', config, results)
                else:
                    db.save_scan(scan_id, 'error', config, results, results.get('error'))
                
                self.task_results[scan_id] = results
                
            except Exception as e:
                logger.error(f"❌ Erreur dans scan_worker: {e}")
                db.save_scan(scan_id, 'error', config, None, str(e))
                self.task_results[scan_id] = {'status': 'error', 'error': str(e)}
            
            finally:
                if scan_id in self.active_tasks:
                    del self.active_tasks[scan_id]
        
        thread = threading.Thread(target=scan_worker, daemon=True)
        thread.start()
        return True
    
    def get_scan_status(self, scan_id: str) -> Dict[str, Any]:
        """Récupère le statut d'un scan"""
        if scan_id in self.task_results:
            return self.task_results[scan_id]
        
        if scan_id in self.active_tasks:
            return {'status': 'running', 'progress': 'En cours...'}
        
        # Vérifier en base de données
        scans = db.get_recent_scans(10)
        for scan in scans:
            if scan['id'] == scan_id:
                return {
                    'status': scan['status'],
                    'results': scan['results'],
                    'error': scan['error_message']
                }
        
        return {'status': 'not_found'}
    
    def cancel_scan(self, scan_id: str) -> bool:
        """Annule un scan en cours"""
        if scan_id in self.active_tasks:
            self.active_tasks[scan_id].cancel()
            return True
        return False

# Instance globale du gestionnaire de tâches
task_manager = SymlinkTaskManager()

def init_symlink_database():
    """Initialise la base de données symlink"""
    global db
    try:
        db = SymlinkDatabase()
        logger.info("✅ Base de données Symlink initialisée")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation base symlink: {e}")
        raise

def register_symlink_routes(app):
    """Enregistre toutes les routes symlink dans l'application Flask"""
    
    @app.route('/symlink')
    def symlink_page():
        """Page principale du Symlink Manager"""
        try:
            config = db.get_config()
            recent_scans = db.get_recent_scans(3)
            return render_template('symlink_tool.html', config=config, recent_scans=recent_scans)
        except Exception as e:
            logger.error(f"❌ Erreur page symlink: {e}")
            flash(f'Erreur: {e}', 'error')
            return render_template('symlink_tool.html', config=DEFAULT_CONFIG, recent_scans=[])
    
    @app.route('/api/symlink/config', methods=['GET', 'POST'])
    def api_symlink_config():
        """API de gestion de la configuration"""
        if request.method == 'GET':
            try:
                config = db.get_config()
                return jsonify({'success': True, 'config': config})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        elif request.method == 'POST':
            try:
                data = request.get_json()
                if db.save_config(data):
                    return jsonify({'success': True, 'message': 'Configuration sauvegardée'})
                else:
                    return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/directories')
    def api_symlink_directories():
        """API pour lister les répertoires disponibles"""
        try:
            config = db.get_config()
            media_path = config.get('media_path', DEFAULT_CONFIG['media_path'])
            
            directories = []
            if os.path.exists(media_path):
                for item in os.listdir(media_path):
                    item_path = os.path.join(media_path, item)
                    if os.path.isdir(item_path):
                        directories.append({
                            'name': item,
                            'path': item_path,
                            'size': len(os.listdir(item_path)) if os.access(item_path, os.R_OK) else 0
                        })
            
            return jsonify({'success': True, 'directories': directories})
            
        except Exception as e:
            logger.error(f"❌ Erreur listage répertoires: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/start', methods=['POST'])
    def api_start_scan():
        """API pour démarrer un nouveau scan"""
        try:
            data = request.get_json()
            scan_id = f"scan_{int(time.time())}"
            
            config = {
                'directories': data.get('directories', []),
                'mode': data.get('mode', 'dry-run'),
                'depth': data.get('depth', 'basic'),
                'workers': data.get('workers', 4)
            }
            
            if task_manager.start_scan(scan_id, config):
                return jsonify({'success': True, 'scan_id': scan_id})
            else:
                return jsonify({'success': False, 'error': 'Scan déjà en cours'}), 400
                
        except Exception as e:
            logger.error(f"❌ Erreur démarrage scan: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/status/<scan_id>')
    def api_scan_status(scan_id):
        """API pour récupérer le statut d'un scan"""
        try:
            status = task_manager.get_scan_status(scan_id)
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            logger.error(f"❌ Erreur statut scan: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/cancel/<scan_id>', methods=['POST'])
    def api_cancel_scan(scan_id):
        """API pour annuler un scan"""
        try:
            if task_manager.cancel_scan(scan_id):
                return jsonify({'success': True, 'message': 'Scan annulé'})
            else:
                return jsonify({'success': False, 'error': 'Scan non trouvé ou déjà terminé'}), 404
        except Exception as e:
            logger.error(f"❌ Erreur annulation scan: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scans/history')
    def api_scans_history():
        """API pour récupérer l'historique des scans"""
        try:
            scans = db.get_recent_scans(10)
            return jsonify({'success': True, 'scans': scans})
        except Exception as e:
            logger.error(f"❌ Erreur historique scans: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/test/services', methods=['POST'])
    def api_test_services():
        """API pour tester les connexions aux services"""
        try:
            data = request.get_json()
            results = {}
            
            # Test Sonarr
            if data.get('sonarr_enabled'):
                try:
                    url = data.get('sonarr_url', '').rstrip('/')
                    api_key = data.get('sonarr_api_key', '')
                    
                    response = requests.get(f"{url}/api/v3/system/status", 
                                          headers={'X-Api-Key': api_key}, 
                                          timeout=5)
                    
                    if response.status_code == 200:
                        results['sonarr'] = {'success': True, 'message': 'Connexion réussie'}
                    else:
                        results['sonarr'] = {'success': False, 'message': f'HTTP {response.status_code}'}
                        
                except Exception as e:
                    results['sonarr'] = {'success': False, 'message': str(e)}
            
            # Test Radarr
            if data.get('radarr_enabled'):
                try:
                    url = data.get('radarr_url', '').rstrip('/')
                    api_key = data.get('radarr_api_key', '')
                    
                    response = requests.get(f"{url}/api/v3/system/status", 
                                          headers={'X-Api-Key': api_key}, 
                                          timeout=5)
                    
                    if response.status_code == 200:
                        results['radarr'] = {'success': True, 'message': 'Connexion réussie'}
                    else:
                        results['radarr'] = {'success': False, 'message': f'HTTP {response.status_code}'}
                        
                except Exception as e:
                    results['radarr'] = {'success': False, 'message': str(e)}
            
            return jsonify({'success': True, 'results': results})
            
        except Exception as e:
            logger.error(f"❌ Erreur test services: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/services/detect', methods=['POST'])
    def api_detect_services():
        """API pour auto-détecter les services Docker"""
        try:
            detected = {}
            
            # Recherche de conteneurs Docker Sonarr/Radarr
            try:
                result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Ports}}'], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        if '\t' in line:
                            name, ports = line.split('\t', 1)
                            name = name.strip()
                            
                            if 'sonarr' in name.lower():
                                # Extraire le port
                                if '8989' in ports:
                                    detected['sonarr'] = {
                                        'url': 'http://localhost:8989',
                                        'container': name
                                    }
                            
                            elif 'radarr' in name.lower():
                                # Extraire le port
                                if '7878' in ports:
                                    detected['radarr'] = {
                                        'url': 'http://localhost:7878',
                                        'container': name
                                    }
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur détection Docker: {e}")
            
            return jsonify({'success': True, 'detected': detected})
            
        except Exception as e:
            logger.error(f"❌ Erreur auto-détection: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    logger.info("🔗 Routes Symlink Manager enregistrées")
