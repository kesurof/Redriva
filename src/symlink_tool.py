#!/usr/bin/env python3
"""
Symlink Manager Tool - Gestionnaire de liens symboliques pour Redriva
Intégration du script advanced_symlink_detector dans l'interface web Redriva

Maintenu via Claude/Copilot - Architecture modulaire simplifiée
"""

import os
import sys
import sqlite3
import threading
import time
import json
import logging
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, render_template

# Configuration des chemins
DB_PATH = os.path.join(os.path.dirname(__file__), '../data/redriva.db')
SYMLINK_DB_PATH = os.path.join(os.path.dirname(__file__), '../data/symlink.db')

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLES DE BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

def init_symlink_database():
    """Initialise la base de données pour le symlink manager"""
    os.makedirs(os.path.dirname(SYMLINK_DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(SYMLINK_DB_PATH)
    cursor = conn.cursor()
    
    # Table de configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symlink_config (
            id INTEGER PRIMARY KEY,
            media_path TEXT DEFAULT '/app/medias',
            max_workers INTEGER DEFAULT 6,
            sonarr_enabled BOOLEAN DEFAULT 0,
            sonarr_host TEXT DEFAULT '',
            sonarr_port INTEGER DEFAULT 8989,
            sonarr_api_key TEXT DEFAULT '',
            radarr_enabled BOOLEAN DEFAULT 0,
            radarr_host TEXT DEFAULT '',
            radarr_port INTEGER DEFAULT 7878,
            radarr_api_key TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des scans (rotation des 3 derniers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symlink_scans (
            id INTEGER PRIMARY KEY,
            scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mode TEXT CHECK(mode IN ('dry-run', 'real')),
            selected_paths TEXT,
            verification_depth TEXT CHECK(verification_depth IN ('basic', 'full')),
            total_analyzed INTEGER DEFAULT 0,
            phase1_ok INTEGER DEFAULT 0,
            phase1_broken INTEGER DEFAULT 0,
            phase1_inaccessible INTEGER DEFAULT 0,
            phase1_small INTEGER DEFAULT 0,
            phase1_io_error INTEGER DEFAULT 0,
            phase2_analyzed INTEGER DEFAULT 0,
            phase2_corrupted INTEGER DEFAULT 0,
            files_deleted INTEGER DEFAULT 0,
            duration REAL,
            status TEXT CHECK(status IN ('running', 'completed', 'cancelled', 'error')),
            results_json TEXT,
            error_message TEXT
        )
    ''')
    
    # Insérer une configuration par défaut si elle n'existe pas
    cursor.execute('SELECT COUNT(*) FROM symlink_config')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO symlink_config (media_path, max_workers) 
            VALUES ('/app/medias', 6)
        ''')
    
    conn.commit()
    conn.close()
    logger.info("Base de données symlink initialisée")

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTATION DE LA CLASSE AdvancedSymlinkChecker
# ═══════════════════════════════════════════════════════════════════════════════

class WebSymlinkChecker:
    """Version adaptée d'AdvancedSymlinkChecker pour l'interface web"""
    
    def __init__(self, max_workers=6, progress_callback=None):
        self.max_workers = max_workers
        self.progress_callback = progress_callback or (lambda x: None)
        self.stop_requested = False
        self.current_stats = {
            'phase': 'idle',
            'progress': 0,
            'current_file': '',
            'phase1_ok': 0,
            'phase1_broken': 0,
            'phase1_inaccessible': 0,
            'phase1_small': 0,
            'phase1_io_error': 0,
            'phase2_analyzed': 0,
            'phase2_corrupted': 0
        }
        self.all_problems = []
        self.deleted_files = []
    
    def update_progress(self, message, **kwargs):
        """Met à jour le statut de progression"""
        self.current_stats.update(kwargs)
        self.progress_callback({
            'message': message,
            'stats': self.current_stats.copy()
        })
    
    def scan_directory_structure(self, base_path: str) -> List[Dict]:
        """Analyse la structure des répertoires avec comptage des symlinks (PREMIER NIVEAU SEULEMENT)"""
        directories = []
        
        try:
            if not os.path.exists(base_path):
                logger.error(f"Chemin inexistant: {base_path}")
                return directories
            
            # Scanner UNIQUEMENT le premier niveau
            for item in os.listdir(base_path):
                if self.stop_requested:
                    break
                    
                item_path = os.path.join(base_path, item)
                
                # Ignorer les fichiers, on ne veut que les dossiers
                if not os.path.isdir(item_path):
                    continue
                
                # Ignorer les dossiers cachés
                if item.startswith('.'):
                    continue
                
                symlink_count = 0
                try:
                    # Compter récursivement les symlinks dans ce dossier
                    for root, dirs, files in os.walk(item_path):
                        if self.stop_requested:
                            break
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.islink(file_path):
                                symlink_count += 1
                                
                except (PermissionError, OSError) as e:
                    logger.warning(f"Erreur accès {item_path}: {e}")
                    symlink_count = -1  # Indicateur d'erreur
                
                directories.append({
                    'name': item,
                    'path': item_path,
                    'symlink_count': symlink_count
                })
        
        except Exception as e:
            logger.error(f"Erreur scan structure: {e}")
        
        # Trier par nombre de symlinks (décroissant)
        directories.sort(key=lambda x: x['symlink_count'] if x['symlink_count'] >= 0 else 0, reverse=True)
        
        return directories
    
    def phase1_scan(self, selected_paths: List[str]) -> Tuple[List[str], List[Dict]]:
        """Phase 1: Vérification basique des liens symboliques"""
        self.update_progress("Démarrage Phase 1 - Vérification basique", phase='phase1')
        
        ok_files = []
        problems = []
        total_files = 0
        processed = 0
        
        # Comptage initial des fichiers
        for path in selected_paths:
            if self.stop_requested:
                break
            for root, dirs, files in os.walk(path):
                total_files += len([f for f in files if os.path.islink(os.path.join(root, f))])
        
        # Traitement des fichiers
        for path in selected_paths:
            if self.stop_requested:
                break
                
            for root, dirs, files in os.walk(path):
                for file in files:
                    if self.stop_requested:
                        break
                        
                    file_path = os.path.join(root, file)
                    if not os.path.islink(file_path):
                        continue
                    
                    processed += 1
                    progress = int((processed / total_files) * 100) if total_files > 0 else 0
                    
                    self.update_progress(
                        f"Analyse: {file}",
                        progress=progress,
                        current_file=file_path
                    )
                    
                    try:
                        target = os.readlink(file_path)
                        
                        # Lien cassé
                        if not os.path.exists(file_path):
                            problems.append({
                                'type': 'broken_link',
                                'path': file_path,
                                'target': target,
                                'reason': 'Cible inexistante'
                            })
                            self.current_stats['phase1_broken'] += 1
                            continue
                        
                        # Fichier inaccessible
                        if not os.access(file_path, os.R_OK):
                            problems.append({
                                'type': 'inaccessible',
                                'path': file_path,
                                'target': target,
                                'reason': 'Permissions insuffisantes'
                            })
                            self.current_stats['phase1_inaccessible'] += 1
                            continue
                        
                        # Fichier vide
                        if os.path.getsize(file_path) == 0:
                            problems.append({
                                'type': 'empty_file',
                                'path': file_path,
                                'target': target,
                                'reason': 'Fichier vide (0 bytes)'
                            })
                            self.current_stats['phase1_small'] += 1
                            continue
                        
                        # Fichier OK
                        ok_files.append(file_path)
                        self.current_stats['phase1_ok'] += 1
                        
                    except OSError as e:
                        problems.append({
                            'type': 'io_error',
                            'path': file_path,
                            'target': target if 'target' in locals() else 'Unknown',
                            'reason': f'Erreur I/O: {str(e)}'
                        })
                        self.current_stats['phase1_io_error'] += 1
        
        self.update_progress("Phase 1 terminée", phase='phase1_complete')
        return ok_files, problems
    
    def phase2_scan(self, ok_files: List[str]) -> List[Dict]:
        """Phase 2: Vérification ffprobe pour corruption"""
        self.update_progress("Démarrage Phase 2 - Vérification ffprobe", phase='phase2')
        
        problems = []
        total_files = len(ok_files)
        
        # Vérifier si ffprobe est disponible
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffprobe non disponible, phase 2 ignorée")
            return problems
        
        for i, file_path in enumerate(ok_files):
            if self.stop_requested:
                break
                
            progress = int((i / total_files) * 100) if total_files > 0 else 0
            self.update_progress(
                f"Vérification ffprobe: {os.path.basename(file_path)}",
                progress=progress,
                current_file=file_path
            )
            
            try:
                # Vérification avec ffprobe
                result = subprocess.run([
                    'ffprobe', '-v', 'error', '-show_entries', 
                    'format=duration', '-of', 'csv=p=0', file_path
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0 or not result.stdout.strip():
                    problems.append({
                        'type': 'corrupted_media',
                        'path': file_path,
                        'target': os.readlink(file_path),
                        'reason': 'Fichier média corrompu (ffprobe failed)'
                    })
                    self.current_stats['phase2_corrupted'] += 1
                else:
                    self.current_stats['phase2_analyzed'] += 1
                    
            except subprocess.TimeoutExpired:
                problems.append({
                    'type': 'corrupted_media',
                    'path': file_path,
                    'target': os.readlink(file_path),
                    'reason': 'Timeout ffprobe (probablement corrompu)'
                })
                self.current_stats['phase2_corrupted'] += 1
            except Exception as e:
                logger.error(f"Erreur ffprobe pour {file_path}: {e}")
        
        self.update_progress("Phase 2 terminée", phase='phase2_complete')
        return problems
    
    def delete_files(self, problems: List[Dict]) -> List[Dict]:
        """Supprime les fichiers problématiques"""
        deleted = []
        
        for problem in problems:
            if self.stop_requested:
                break
                
            try:
                os.unlink(problem['path'])
                deleted.append(problem)
                logger.info(f"Supprimé: {problem['path']}")
            except Exception as e:
                logger.error(f"Erreur suppression {problem['path']}: {e}")
        
        return deleted
    
    def get_container_ip(self, container_id: str, network: str = None) -> Optional[str]:
        """Récupère l'IP d'un conteneur Docker avec réseau spécifique"""
        try:
            if network:
                cmd = f"docker inspect {container_id} --format='{{{{.NetworkSettings.Networks.{network}.IPAddress}}}}'"
            else:
                # Fallback - première IP trouvée
                cmd = f"docker inspect {container_id} --format='{{{{range .NetworkSettings.Networks}}{{{{.IPAddress}}}}{{{{end}}}}'"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Erreur IP container {container_id}: {e}")
        return None

    def get_api_key(self, service: str, custom_path: str = None) -> Optional[str]:
        """Récupère la clé API d'un service depuis sa configuration"""
        try:
            if custom_path:
                config_path = custom_path
            else:
                # Chemins par défaut basés sur votre structure
                settings_storage = os.environ.get('SETTINGS_STORAGE', '/opt/seedbox/docker')
                current_user = os.environ.get('USER', 'kesurof')
                config_path = f"{settings_storage}/docker/{current_user}/{service}/config/config.xml"
            
            if not os.path.exists(config_path):
                logger.warning(f"Config {service} introuvable: {config_path}")
                return None
                
            cmd = f"sed -n 's/.*<ApiKey>\\(.*\\)<\\/ApiKey>.*/\\1/p' '{config_path}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else None
            
        except Exception as e:
            logger.error(f"Erreur API key {service}: {e}")
            return None

    def detect_docker_services(self) -> Dict:
        """Auto-détection avancée des services Sonarr/Radarr via Docker"""
        services = {'sonarr': None, 'radarr': None}
        
        try:
            import subprocess
            import json
            
            # ✅ CORRECTION : Vérifier Docker disponible d'abord
            docker_check = subprocess.run(['which', 'docker'], capture_output=True)
            if docker_check.returncode != 0:
                logger.info("Docker CLI non disponible - auto-détection désactivée")
                return services
            
            # Lister les conteneurs Docker actifs
            result = subprocess.run(
                ['docker', 'ps', '--format', 'json'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("Docker non disponible ou erreur")
                return services
            
            # ✅ CORRECTION : Vérifier que la sortie n'est pas vide
            if not result.stdout.strip():
                logger.info("Aucun conteneur Docker détecté")
                return services
            
            # Parser les conteneurs
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    # ✅ CORRECTION : Gestion des erreurs JSON
                    container = json.loads(line)
                    name = container.get('Names', '').lower()
                    image = container.get('Image', '').lower()
                    ports = container.get('Ports', '')
                    container_id = container.get('ID', '')
                    
                    # Détection Sonarr
                    if ('sonarr' in name or 'sonarr' in image) and '8989' in ports:
                        ip = self.get_container_ip(container_id, 'traefik_proxy') or self.get_container_ip(container_id)
                        api_key = self.get_api_key('sonarr')
                        
                        services['sonarr'] = {
                            'host': ip or 'localhost',
                            'port': 8989,
                            'api_key': api_key,
                            'container_name': name,
                            'auto_detected': True
                        }
                    
                    # Détection Radarr
                    if ('radarr' in name or 'radarr' in image) and '7878' in ports:
                        ip = self.get_container_ip(container_id, 'traefik_proxy') or self.get_container_ip(container_id)
                        api_key = self.get_api_key('radarr')
                        
                        services['radarr'] = {
                            'host': ip or 'localhost',
                            'port': 7878,
                            'api_key': api_key,
                            'container_name': name,
                            'auto_detected': True
                        }
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Erreur parsing JSON Docker: {line[:50]}... - {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erreur détection Docker: {e}")
        
        return services

    def trigger_media_scans(self, config: Dict):
        """Déclenche les scans Sonarr/Radarr si configurés"""
        if config.get('sonarr_enabled'):
            self._trigger_sonarr_scan(config)
        
        if config.get('radarr_enabled'):
            self._trigger_radarr_scan(config)
    
    def _trigger_sonarr_scan(self, config: Dict):
        """Déclenche un scan Sonarr"""
        try:
            import requests
            
            # ✅ CORRECTION : Assurer que le port est bien une chaîne
            host = config.get('sonarr_host', 'localhost')
            port = str(config.get('sonarr_port', 8989))  # Convertir en string
            api_key = config.get('sonarr_api_key', '')
            
            if not api_key:
                logger.warning("API key Sonarr manquante, scan ignoré")
                return
                
            url = f"http://{host}:{port}/api/v3/command"
            headers = {'X-Api-Key': api_key}  # ✅ API key seulement
            data = {'name': 'RescanSeries'}
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            if response.status_code == 201:
                logger.info("Scan Sonarr déclenché avec succès")
            else:
                logger.warning(f"Erreur scan Sonarr: {response.status_code}")
        except Exception as e:
            logger.error(f"Erreur déclenchement scan Sonarr: {e}")
    
    def _trigger_radarr_scan(self, config: Dict):
        """Déclenche un scan Radarr"""
        try:
            import requests
            
            # ✅ CORRECTION : Assurer que le port est bien une chaîne  
            host = config.get('radarr_host', 'localhost')
            port = str(config.get('radarr_port', 7878))  # Convertir en string
            api_key = config.get('radarr_api_key', '')
            
            if not api_key:
                logger.warning("API key Radarr manquante, scan ignoré")
                return
                
            url = f"http://{host}:{port}/api/v3/command"
            headers = {'X-Api-Key': api_key}  # ✅ API key seulement
            data = {'name': 'RescanMovie'}
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            if response.status_code == 201:
                logger.info("Scan Radarr déclenché avec succès")
            else:
                logger.warning(f"Erreur scan Radarr: {response.status_code}")
        except Exception as e:
            logger.error(f"Erreur déclenchement scan Radarr: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIONNAIRE DE TÂCHES ASYNCHRONES
# ═══════════════════════════════════════════════════════════════════════════════

class SymlinkTaskManager:
    """Gestionnaire de tâches asynchrones pour les scans symlink"""
    
    def __init__(self):
        self.current_task = None
        self.task_status = {
            'running': False,
            'progress': {},
            'scan_id': None,
            'start_time': None
        }
        self.task_results = {}
    
    def start_scan(self, scan_config: Dict) -> str:
        """Démarre un nouveau scan"""
        if self.task_status['running']:
            raise RuntimeError("Un scan est déjà en cours")
        
        scan_id = str(int(time.time()))
        self.task_status = {
            'running': True,
            'progress': {'message': 'Initialisation...', 'stats': {}},
            'scan_id': scan_id,
            'start_time': time.time()
        }
        
        # Créer l'entrée dans la base de données
        self._create_scan_record(scan_id, scan_config)
        
        # Lancer la tâche en arrière-plan
        self.current_task = threading.Thread(
            target=self._execute_scan,
            args=(scan_id, scan_config),
            daemon=True
        )
        self.current_task.start()
        
        return scan_id
    
    def cancel_scan(self, scan_id: str) -> bool:
        """Annule le scan en cours"""
        if not self.task_status['running'] or self.task_status['scan_id'] != scan_id:
            return False
        
        # Marquer pour arrêt
        if hasattr(self, 'checker') and self.checker:
            self.checker.stop_requested = True
        
        self._update_scan_status(scan_id, 'cancelled')
        return True
    
    def get_scan_status(self, scan_id: str) -> Dict:
        """Récupère le statut d'un scan"""
        if self.task_status['scan_id'] == scan_id:
            return self.task_status.copy()
        
        # Scan terminé, récupérer depuis la base
        return self._get_scan_from_db(scan_id)
    
    def _create_scan_record(self, scan_id: str, config: Dict):
        """Crée l'enregistrement de scan dans la DB"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO symlink_scans (
                id, mode, selected_paths, verification_depth, status
            ) VALUES (?, ?, ?, ?, 'running')
        ''', (
            scan_id,
            config['mode'],
            json.dumps(config['selected_paths']),
            config['verification_depth']
        ))
        
        conn.commit()
        conn.close()
    
    def _execute_scan(self, scan_id: str, config: Dict):
        """Exécute le scan dans un thread séparé"""
        try:
            self.checker = WebSymlinkChecker(
                max_workers=config['max_workers'],
                progress_callback=self._update_progress
            )
            
            start_time = time.time()
            
            # Phase 1
            ok_files, phase1_problems = self.checker.phase1_scan(config['selected_paths'])
            
            # Phase 2 (si demandée)
            phase2_problems = []
            if config['verification_depth'] == 'full' and ok_files:
                phase2_problems = self.checker.phase2_scan(ok_files)
            
            # Regroupement des problèmes
            all_problems = phase1_problems + phase2_problems
            
            # Suppression (si mode real)
            deleted_files = []
            if config['mode'] == 'real' and all_problems:
                deleted_files = self.checker.delete_files(all_problems)
            
            # Mise à jour finale
            duration = time.time() - start_time
            self._finalize_scan(scan_id, all_problems, deleted_files, duration)
            
            # Déclencher les scans média
            if deleted_files:
                scan_config = self._get_config()
                self.checker.trigger_media_scans(scan_config)
            
        except Exception as e:
            logger.error(f"Erreur dans le scan {scan_id}: {e}")
            self._update_scan_status(scan_id, 'error', str(e))
        finally:
            self.task_status['running'] = False
            self.checker = None
    
    def _update_progress(self, progress_data: Dict):
        """Met à jour le statut de progression"""
        self.task_status['progress'] = progress_data
    
    def _finalize_scan(self, scan_id: str, problems: List, deleted: List, duration: float):
        """Finalise le scan avec les résultats"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        stats = self.checker.current_stats
        
        cursor.execute('''
            UPDATE symlink_scans SET
                total_analyzed = ?,
                phase1_ok = ?,
                phase1_broken = ?,
                phase1_inaccessible = ?,
                phase1_small = ?,
                phase1_io_error = ?,
                phase2_analyzed = ?,
                phase2_corrupted = ?,
                files_deleted = ?,
                duration = ?,
                status = 'completed',
                results_json = ?
            WHERE id = ?
        ''', (
            stats['phase1_ok'] + stats['phase1_broken'] + stats['phase1_inaccessible'] + 
            stats['phase1_small'] + stats['phase1_io_error'],
            stats['phase1_ok'],
            stats['phase1_broken'],
            stats['phase1_inaccessible'],
            stats['phase1_small'],
            stats['phase1_io_error'],
            stats['phase2_analyzed'],
            stats['phase2_corrupted'],
            len(deleted),
            duration,
            json.dumps({'problems': problems, 'deleted': deleted}),
            scan_id
        ))
        
        conn.commit()
        conn.close()
        
        # Rotation - garder seulement les 3 derniers
        self._cleanup_old_scans()
    
    def _update_scan_status(self, scan_id: str, status: str, error_msg: str = None):
        """Met à jour le statut d'un scan"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        if error_msg:
            cursor.execute(
                'UPDATE symlink_scans SET status = ?, error_message = ? WHERE id = ?',
                (status, error_msg, scan_id)
            )
        else:
            cursor.execute(
                'UPDATE symlink_scans SET status = ? WHERE id = ?',
                (status, scan_id)
            )
        
        conn.commit()
        conn.close()
    
    def _get_scan_from_db(self, scan_id: str) -> Dict:
        """Récupère un scan depuis la base de données"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM symlink_scans WHERE id = ?', (scan_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {'error': 'Scan not found'}
        
        return {
            'running': row[16] == 'running',  # status
            'scan_id': row[0],
            'status': row[16],
            'progress': {'message': 'Terminé' if row[16] == 'completed' else 'Erreur'},
            'results': json.loads(row[17]) if row[17] else {}  # results_json
        }
    
    def _cleanup_old_scans(self):
        """Nettoie les anciens scans (garde les 3 derniers)"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM symlink_scans 
            WHERE id NOT IN (
                SELECT id FROM symlink_scans 
                ORDER BY scan_date DESC 
                LIMIT 3
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_config(self) -> Dict:
        """Récupère la configuration depuis la base"""
        conn = sqlite3.connect(SYMLINK_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM symlink_config ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        return {
            'sonarr_enabled': bool(row[2]),
            'sonarr_host': row[3],
            'sonarr_port': row[4],
            'sonarr_api_key': row[5],
            'radarr_enabled': bool(row[6]),
            'radarr_host': row[7],
            'radarr_port': row[8],
            'radarr_api_key': row[9]
        }

# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS API
# ═══════════════════════════════════════════════════════════════════════════════

# Instance globale du gestionnaire de tâches
task_manager = SymlinkTaskManager()

def register_symlink_routes(app: Flask):
    """Enregistre les routes symlink dans l'application Flask"""
    
    @app.route('/symlink')
    def symlink_manager():
        """Page principale du gestionnaire de symlink"""
        return render_template('symlink_tool.html')
    
    @app.route('/api/symlink/config', methods=['GET'])
    def get_symlink_config():
        """Récupère la configuration actuelle"""
        try:
            conn = sqlite3.connect(SYMLINK_DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM symlink_config ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()
            conn.close()
            
            if row:
                config = {
                    'media_path': row[1],
                    'max_workers': row[2],
                    'sonarr_enabled': bool(row[3]),
                    'sonarr_host': row[4],
                    'sonarr_port': row[5],
                    'sonarr_api_key': row[6],
                    'radarr_enabled': bool(row[7]),
                    'radarr_host': row[8],
                    'radarr_port': row[9],
                    'radarr_api_key': row[10]
                }
            else:
                config = {
                    'media_path': '/app/medias',
                    'max_workers': 6,
                    'sonarr_enabled': False,
                    'sonarr_host': '',
                    'sonarr_port': 8989,
                    'sonarr_api_key': '',
                    'radarr_enabled': False,
                    'radarr_host': '',
                    'radarr_port': 7878,
                    'radarr_api_key': ''
                }
            
            return jsonify({'success': True, 'config': config})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/config', methods=['POST'])
    def save_symlink_config():
        """Sauvegarde la configuration"""
        try:
            data = request.get_json()
            
            conn = sqlite3.connect(SYMLINK_DB_PATH)
            cursor = conn.cursor()
            
            # Mise à jour ou insertion
            cursor.execute('''
                INSERT OR REPLACE INTO symlink_config (
                    id, media_path, max_workers, sonarr_enabled, sonarr_host, 
                    sonarr_port, sonarr_api_key, radarr_enabled, radarr_host, 
                    radarr_port, radarr_api_key, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                data['media_path'],
                data['max_workers'],
                data['sonarr_enabled'],
                data['sonarr_host'],
                data['sonarr_port'],
                data['sonarr_api_key'],
                data['radarr_enabled'],
                data['radarr_host'],
                data['radarr_port'],
                data['radarr_api_key']
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/directories', methods=['GET'])
    def get_directories():
        """Liste les répertoires disponibles avec compteurs"""
        try:
            # Récupérer le chemin depuis la config
            conn = sqlite3.connect(SYMLINK_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT media_path FROM symlink_config ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()
            conn.close()
            
            media_path = row[0] if row else '/app/medias'
            
            if not os.path.exists(media_path):
                return jsonify({
                    'success': False, 
                    'error': f'Chemin des médias introuvable: {media_path}'
                })
            
            checker = WebSymlinkChecker()
            directories = checker.scan_directory_structure(media_path)
            
            return jsonify({'success': True, 'directories': directories})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/start', methods=['POST'])
    def start_scan():
        """Démarre un nouveau scan"""
        try:
            data = request.get_json()
            
            # Récupérer la config pour max_workers
            conn = sqlite3.connect(SYMLINK_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT max_workers FROM symlink_config ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()
            conn.close()
            
            scan_config = {
                'selected_paths': data['selected_paths'],
                'mode': data['mode'],
                'verification_depth': data['verification_depth'],
                'max_workers': row[0] if row else 6
            }
            
            scan_id = task_manager.start_scan(scan_config)
            
            return jsonify({'success': True, 'scan_id': scan_id})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/status/<scan_id>', methods=['GET'])
    def get_scan_status(scan_id):
        """Récupère le statut d'un scan"""
        try:
            status = task_manager.get_scan_status(scan_id)
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scan/cancel/<scan_id>', methods=['POST'])
    def cancel_scan(scan_id):
        """Annule un scan en cours"""
        try:
            success = task_manager.cancel_scan(scan_id)
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/scans/history', methods=['GET'])
    def get_scans_history():
        """Récupère l'historique des 3 derniers scans"""
        try:
            conn = sqlite3.connect(SYMLINK_DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, scan_date, mode, verification_depth, total_analyzed,
                       phase1_broken, phase1_inaccessible, phase1_small, phase1_io_error,
                       phase2_corrupted, files_deleted, duration, status
                FROM symlink_scans 
                ORDER BY scan_date DESC 
                LIMIT 3
            ''')
            
            scans = []
            for row in cursor.fetchall():
                scans.append({
                    'id': row[0],
                    'date': row[1],
                    'mode': row[2],
                    'verification_depth': row[3],
                    'total_analyzed': row[4],
                    'total_problems': (row[5] or 0) + (row[6] or 0) + (row[7] or 0) + (row[8] or 0) + (row[9] or 0),
                    'files_deleted': row[10],
                    'duration': row[11],
                    'status': row[12]
                })
            
            conn.close()
            return jsonify({'success': True, 'scans': scans})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/test/services', methods=['POST'])
    def test_services():
        """Teste les connexions Sonarr/Radarr"""
        try:
            data = request.get_json()
            results = {}
            
            # Test Sonarr
            if data.get('test_sonarr'):
                try:
                    import requests
                    url = f"http://{data['sonarr_host']}:{data['sonarr_port']}/api/v3/system/status"
                    headers = {'X-Api-Key': data['sonarr_api_key']}
                    response = requests.get(url, headers=headers, timeout=10)
                    results['sonarr'] = {
                        'success': response.status_code == 200,
                        'message': 'Connexion réussie' if response.status_code == 200 else f'Erreur {response.status_code}'
                    }
                except Exception as e:
                    results['sonarr'] = {'success': False, 'message': str(e)}
            
            # Test Radarr
            if data.get('test_radarr'):
                try:
                    import requests
                    url = f"http://{data['radarr_host']}:{data['radarr_port']}/api/v3/system/status"
                    headers = {'X-Api-Key': data['radarr_api_key']}
                    response = requests.get(url, headers=headers, timeout=10)
                    results['radarr'] = {
                        'success': response.status_code == 200,
                        'message': 'Connexion réussie' if response.status_code == 200 else f'Erreur {response.status_code}'
                    }
                except Exception as e:
                    results['radarr'] = {'success': False, 'message': str(e)}
            
            return jsonify({'success': True, 'results': results})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/symlink/services/detect', methods=['POST'])
    def detect_services():
        """Auto-détection des services Sonarr/Radarr via Docker"""
        try:
            checker = WebSymlinkChecker()
            services = checker.detect_docker_services()
            
            return jsonify({
                'success': True,
                'services': services,
                'message': 'Détection terminée'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# Initialisation au chargement du module
init_symlink_database()
