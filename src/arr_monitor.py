#!/usr/bin/env python3
"""
Arr Monitor - Module de surveillance Sonarr/Radarr intégré à Redriva
Détecte et corrige automatiquement les téléchargements échoués ou bloqués
Adapté pour utiliser la configuration et les logs centralisés de Redriva
"""

import requests
import threading
import time
import platform
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Import du gestionnaire de configuration Redriva
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

class ArrMonitor:
    """
    Classe de surveillance Sonarr/Radarr intégrée à Redriva
    Utilise la configuration centralisée et le système de logs de Redriva
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialise le moniteur avec la configuration Redriva
        
        Args:
            config_manager: Instance du gestionnaire de configuration Redriva
        """
        self.config_manager = config_manager
        self.session = requests.Session()
        self.version = "2.0.0"  # Version intégrée Redriva
        self._setup_session()
        
        # État du moniteur
        self.is_running = False
        self.monitor_thread = None
        
        logger.info("🔧 Arr Monitor initialisé pour Redriva")
    
    def _setup_session(self):
        """Configure la session HTTP avec optimisations"""
        # Timeout adaptatif selon l'architecture
        if platform.machine() in ['aarch64', 'arm64']:
            self.session.timeout = 15
            logger.info("🔧 Optimisations ARM64 activées")
        else:
            self.session.timeout = 10
        
        # Headers optimisés
        self.session.headers.update({
            'User-Agent': f'Redriva-ArrMonitor/{self.version} ({platform.machine()}; {platform.system()})'
        })
    
    def get_sonarr_config(self) -> Optional[Dict[str, Any]]:
        """Récupère la configuration Sonarr depuis Redriva"""
        config = self.config_manager.config
        sonarr_config = config.get('sonarr', {})
        
        if not sonarr_config.get('enabled', False):
            return None
            
        if not sonarr_config.get('url') or not sonarr_config.get('api_key'):
            logger.warning("⚠️ Configuration Sonarr incomplète")
            return None
            
        return sonarr_config
    
    def get_radarr_config(self) -> Optional[Dict[str, Any]]:
        """Récupère la configuration Radarr depuis Redriva"""
        config = self.config_manager.config
        radarr_config = config.get('radarr', {})
        
        if not radarr_config.get('enabled', False):
            return None
            
        if not radarr_config.get('url') or not radarr_config.get('api_key'):
            logger.warning("⚠️ Configuration Radarr incomplète")
            return None
            
        return radarr_config
    
    def test_connection(self, app_name: str, url: str, api_key: str) -> bool:
        """Test la connexion à l'API d'une application"""
        try:
            response = self.session.get(
                f"{url}/api/v3/system/status",
                headers={'X-Api-Key': api_key}
            )
            
            if response.status_code == 200:
                logger.info(f"✅ {app_name} connexion réussie")
                return True
            else:
                logger.error(f"❌ {app_name} erreur connexion: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception connexion: {e}")
            return False
    
    def get_queue(self, app_name: str, url: str, api_key: str) -> List[Dict[str, Any]]:
        """Récupère la queue des téléchargements avec pagination complète"""
        try:
            all_items = []
            page = 1
            page_size = 250
            
            while True:
                response = self.session.get(
                    f"{url}/api/v3/queue",
                    headers={'X-Api-Key': api_key},
                    params={
                        'page': page,
                        'pageSize': page_size,
                        'includeUnknownSeriesItems': 'true' if app_name.lower() == 'sonarr' else None
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ {app_name} erreur récupération queue: {response.status_code}")
                    break
                
                data = response.json()
                records = data.get('records', [])
                
                if not records:
                    break
                
                all_items.extend(records)
                
                # Vérifier s'il y a d'autres pages
                if len(records) < page_size:
                    break
                
                page += 1
            
            logger.debug(f"📋 {app_name} queue récupérée: {len(all_items)} éléments")
            return all_items
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception récupération queue: {e}")
            return []
    
    def get_history(self, app_name: str, url: str, api_key: str, since_hours: int = 24) -> List[Dict[str, Any]]:
        """Récupère l'historique des téléchargements"""
        try:
            since_date = datetime.now() - timedelta(hours=since_hours)
            
            response = self.session.get(
                f"{url}/api/v3/history",
                headers={'X-Api-Key': api_key},
                params={
                    'page': 1,
                    'pageSize': 100,
                    'since': since_date.isoformat()
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('records', [])
            else:
                logger.error(f"❌ {app_name} erreur récupération historique: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception récupération historique: {e}")
            return []
    
    def blocklist_and_search(self, app_name: str, url: str, api_key: str, download_id: int) -> bool:
        """Bloque la release défaillante et lance une nouvelle recherche"""
        try:
            # Bloquer la release
            blocklist_response = self.session.put(
                f"{url}/api/v3/queue/blocklist",
                headers={'X-Api-Key': api_key},
                json={'ids': [download_id]}
            )
            
            if blocklist_response.status_code not in [200, 204]:
                logger.error(f"❌ {app_name} erreur blocklist: {blocklist_response.status_code}")
                return False
            
            # Supprimer de la queue
            delete_response = self.session.delete(
                f"{url}/api/v3/queue/{download_id}",
                headers={'X-Api-Key': api_key},
                params={'removeFromClient': 'true', 'blocklist': 'false'}
            )
            
            if delete_response.status_code not in [200, 204]:
                logger.warning(f"⚠️ {app_name} erreur suppression queue: {delete_response.status_code}")
            
            logger.info(f"✅ {app_name} release bloquée et supprimée: ID {download_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception blocklist: {e}")
            return False
    
    def trigger_missing_search(self, app_name: str, url: str, api_key: str) -> bool:
        """Lance une recherche pour les éléments manqués"""
        try:
            endpoint = "wantedmissing" if app_name.lower() == "sonarr" else "wanted/missing"
            
            response = self.session.post(
                f"{url}/api/v3/command",
                headers={'X-Api-Key': api_key},
                json={'name': 'MissingEpisodeSearch' if app_name.lower() == 'sonarr' else 'MissingMovieSearch'}
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ {app_name} recherche manqués lancée")
                return True
            else:
                logger.error(f"❌ {app_name} erreur recherche manqués: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception recherche manqués: {e}")
            return False
    
    def remove_download(self, app_name: str, url: str, api_key: str, download_id: int) -> bool:
        """Supprime un téléchargement de la queue"""
        try:
            response = self.session.delete(
                f"{url}/api/v3/queue/{download_id}",
                headers={'X-Api-Key': api_key},
                params={'removeFromClient': 'true', 'blocklist': 'false'}
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ {app_name} téléchargement supprimé: ID {download_id}")
                return True
            else:
                logger.error(f"❌ {app_name} erreur suppression: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {app_name} exception suppression: {e}")
            return False
    
    def is_download_failed(self, item: Dict[str, Any]) -> bool:
        """Vérifie si un téléchargement a une erreur spécifique qBittorrent"""
        error_message = item.get('errorMessage', '')
        
        # Détection stricte : seulement l'erreur qBittorrent spécifique
        is_qbittorrent_error = (
            error_message and "qBittorrent is reporting an error" in error_message
        )
        
        if is_qbittorrent_error:
            logger.debug(f"🚨 Erreur qBittorrent détectée: {item.get('title', 'Inconnu')}")
        
        return is_qbittorrent_error
    
    def process_application(self, app_name: str, app_config: Dict[str, Any]) -> int:
        """
        Traite une application (Sonarr ou Radarr)
        
        Returns:
            int: Nombre d'éléments traités
        """
        url = app_config.get('url')
        api_key = app_config.get('api_key')
        
        logger.info(f"🔍 Analyse de {app_name}...")
        
        # Test de connexion
        if not self.test_connection(app_name, url, api_key):
            return 0
        
        # Récupération de la queue
        queue = self.get_queue(app_name, url, api_key)
        if not queue:
            logger.info(f"📋 {app_name} queue vide")
            return 0
        
        logger.info(f"📋 {app_name} {len(queue)} éléments en queue")
        
        # Statistiques des statuts pour diagnostic
        status_count = {}
        for item in queue:
            status = item.get('status', 'unknown')
            status_count[status] = status_count.get(status, 0) + 1
        
        logger.debug(f"📊 {app_name} Statuts: {dict(sorted(status_count.items()))}")
        
        processed_items = 0
        
        for item in queue:
            if self.is_download_failed(item):
                download_id = item.get('id')
                title = item.get('title', 'Inconnu')
                
                logger.warning(f"🚨 {app_name} erreur détectée: {title}")
                
                # Bloquer et relancer la recherche
                if self.blocklist_and_search(app_name, url, api_key, download_id):
                    processed_items += 1
                    logger.info(f"✅ {app_name} correction appliquée: {title}")
        
        if processed_items > 0:
            logger.info(f"🔧 {app_name} {processed_items} éléments corrigés")
            # Lancer une recherche pour les manqués après corrections
            self.trigger_missing_search(app_name, url, api_key)
        else:
            logger.info(f"✅ {app_name} aucune erreur détectée")
        
        return processed_items
    
    def run_cycle(self) -> Dict[str, int]:
        """
        Exécute un cycle complet de surveillance
        
        Returns:
            Dict[str, int]: Statistiques du cycle (app_name -> nb_corrections)
        """
        logger.info("🚀 Début du cycle de surveillance Arr")
        
        results = {}
        
        # Traitement Sonarr
        sonarr_config = self.get_sonarr_config()
        if sonarr_config:
            try:
                results['sonarr'] = self.process_application('Sonarr', sonarr_config)
            except Exception as e:
                logger.error(f"❌ Erreur traitement Sonarr: {e}")
                results['sonarr'] = 0
        
        # Traitement Radarr
        radarr_config = self.get_radarr_config()
        if radarr_config:
            try:
                results['radarr'] = self.process_application('Radarr', radarr_config)
            except Exception as e:
                logger.error(f"❌ Erreur traitement Radarr: {e}")
                results['radarr'] = 0
        
        total_corrections = sum(results.values())
        logger.info(f"✅ Cycle terminé - {total_corrections} corrections appliquées")
        
        return results
    
    def start_monitoring(self, interval: int = 300) -> bool:
        """
        Démarre la surveillance continue en arrière-plan
        
        Args:
            interval: Intervalle en secondes entre les cycles
            
        Returns:
            bool: True si démarré avec succès
        """
        if self.is_running:
            logger.warning("⚠️ Surveillance Arr déjà en cours")
            return False
        
        def monitor_loop():
            """Boucle de surveillance"""
            logger.info(f"🔄 Surveillance Arr démarrée (intervalle: {interval}s)")
            
            while self.is_running:
                try:
                    self.run_cycle()
                    
                    # Attente avec vérification d'arrêt
                    for _ in range(interval):
                        if not self.is_running:
                            break
                        time.sleep(1)
                        
                except Exception as e:
                    logger.error(f"❌ Erreur cycle surveillance: {e}")
                    time.sleep(30)  # Attente plus courte en cas d'erreur
            
            logger.info("🛑 Surveillance Arr arrêtée")
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        return True
    
    def stop_monitoring(self) -> bool:
        """
        Arrête la surveillance continue
        
        Returns:
            bool: True si arrêté avec succès
        """
        if not self.is_running:
            logger.warning("⚠️ Surveillance Arr déjà arrêtée")
            return False
        
        logger.info("🛑 Arrêt surveillance Arr...")
        self.is_running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du moniteur
        
        Returns:
            Dict contenant les informations de statut
        """
        return {
            'running': self.is_running,
            'sonarr_enabled': self.get_sonarr_config() is not None,
            'radarr_enabled': self.get_radarr_config() is not None,
            'version': self.version
        }
    
    def diagnose_queue(self, app_name: str) -> Dict[str, Any]:
        """
        Mode diagnostic pour analyser la queue en détail
        
        Args:
            app_name: 'sonarr' ou 'radarr'
            
        Returns:
            Dict contenant les statistiques détaillées
        """
        if app_name.lower() == 'sonarr':
            app_config = self.get_sonarr_config()
            display_name = 'Sonarr'
        elif app_name.lower() == 'radarr':
            app_config = self.get_radarr_config()
            display_name = 'Radarr'
        else:
            return {'error': 'Application non supportée'}
        
        if not app_config:
            return {'error': f'{display_name} non configuré ou désactivé'}
        
        url = app_config.get('url')
        api_key = app_config.get('api_key')
        
        logger.info(f"🔬 DIAGNOSTIC {display_name}...")
        
        # Test de connexion
        if not self.test_connection(display_name, url, api_key):
            return {'error': f'Connexion {display_name} échouée'}
        
        # Récupération de la queue
        queue = self.get_queue(display_name, url, api_key)
        if not queue:
            return {
                'total_items': 0,
                'status_breakdown': {},
                'error_items': [],
                'errors_detected': 0
            }
        
        # Analyse des statuts
        status_count = {}
        error_items = []
        
        for item in queue:
            status = item.get('status', 'unknown')
            status_count[status] = status_count.get(status, 0) + 1
            
            if self.is_download_failed(item):
                error_items.append({
                    'id': item.get('id'),
                    'title': item.get('title', 'Inconnu'),
                    'status': status,
                    'errorMessage': item.get('errorMessage', '')
                })
        
        result = {
            'total_items': len(queue),
            'status_breakdown': status_count,
            'error_items': error_items,
            'errors_detected': len(error_items)
        }
        
        logger.info(f"📊 {display_name} DIAGNOSTIC: {len(queue)} éléments, {len(error_items)} erreurs")
        
        return result


# Instance globale pour l'intégration dans Redriva
_arr_monitor_instance = None

def get_arr_monitor(config_manager: ConfigManager = None) -> ArrMonitor:
    """
    Récupère l'instance singleton du moniteur Arr
    
    Args:
        config_manager: Instance du gestionnaire de configuration Redriva
        
    Returns:
        ArrMonitor: Instance du moniteur
    """
    global _arr_monitor_instance
    
    if _arr_monitor_instance is None:
        if config_manager is None:
            config_manager = ConfigManager()
        _arr_monitor_instance = ArrMonitor(config_manager)
    
    return _arr_monitor_instance
