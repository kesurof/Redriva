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
from error_types_manager import ErrorTypesManager

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
        self.version = "2.1.0"  # Version avec gestion multi-erreurs
        self._setup_session()
        
        # Gestionnaire de types d'erreurs
        self.error_types_manager = ErrorTypesManager(config_manager)

        # État du moniteur
        self.is_running = False
        self.monitor_thread = None
        # Prevent concurrent run_cycle executions
        self._run_lock = threading.Lock()
        # Background monitoring internals
        self._monitor_thread = None
        self._monitor_interval = 30
        self._stop_event = threading.Event()
        # Default per-request timeout (seconds) to avoid blocking the cycle
        self.request_timeout = 12

        logger.info("🔧 Arr Monitor initialisé pour Redriva avec gestion multi-erreurs")
    
    def _setup_session(self):
        """Configure la session HTTP avec optimisations"""
        # Timeout adaptatif selon l'architecture
        if platform.machine() in ['aarch64', 'arm64']:
            self.request_timeout = 15
            logger.info("🔧 Optimisations ARM64 activées")
        else:
            self.request_timeout = 10
        
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
                headers={'X-Api-Key': api_key},
                timeout=self.request_timeout
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
                    },
                    timeout=self.request_timeout
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
            , timeout=self.request_timeout)
            
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
        """Bloque la release défaillante, la supprime et lance une nouvelle recherche.

        Retourne dict {'status': 'ok'|'error', 'message': str} pour affichage UI/logs.
        """
        try:
            headers = {'X-Api-Key': api_key}

            # Supprimer en demandant la blocklist côté serveur (beaucoup d'API supportent ce paramètre)
            # Attempt DELETE with retries/backoff to handle transient network issues
            delete_resp = None
            last_exc = None
            for attempt in range(1, 4):
                try:
                    delete_resp = self.session.delete(
                        f"{url}/api/v3/queue/{download_id}",
                        headers=headers,
                        params={'removeFromClient': 'true', 'blocklist': 'true'},
                        timeout=self.request_timeout
                    )
                    break
                except requests.exceptions.RequestException as e:
                    last_exc = e
                    wait = attempt * 2
                    logger.warning(f"Tentative {attempt} échec DELETE download_id={download_id}: {e} - retrying in {wait}s")
                    time.sleep(wait)

            if delete_resp is None and last_exc is not None:
                # All retries failed
                msg = f"{app_name} blocklist+delete failed after retries: {last_exc}"
                logger.error(msg)
                return {'status': 'error', 'message': msg}

            if delete_resp.status_code not in [200, 204]:
                msg = f"{app_name} blocklist+delete failed ({delete_resp.status_code})"
                body = None
                try:
                    body = delete_resp.text
                except Exception:
                    try:
                        body = delete_resp.content.decode('utf-8', errors='replace')
                    except Exception:
                        body = '<unreadable body>'
                logger.error(msg + f" body:{body}")

                # Fallback: if 404 or not found, try to locate matching queue entry by downloadId/title
                try:
                    logger.info(f"🔎 Tentative fallback: recherche dans la queue pour download_id={download_id}")
                    queue_items = self.get_queue(app_name, url, api_key)
                    cand = str(download_id).lower() if download_id is not None else None
                    matches = []
                    for qi in queue_items:
                        try:
                            qid = str(qi.get('id')) if qi.get('id') is not None else ''
                            qdid = str(qi.get('downloadId') or qi.get('downloadid') or '')
                            title = str(qi.get('title') or '')
                            if cand and (qid.lower() == cand or qdid.lower() == cand or cand in title.lower()):
                                matches.append(qi)
                        except Exception:
                            continue

                    if matches:
                        logger.info(f"🔎 Fallback: trouvé {len(matches)} matching queue entries, tentative suppression via queue id")
                        for m in matches:
                            mid = m.get('id')
                            try:
                                logger.info(f"🔁 Fallback DELETE attempt for queue id={mid}")
                                resp2 = self.session.delete(f"{url}/api/v3/queue/{mid}", headers=headers, params={'removeFromClient': 'true', 'blocklist': 'true'}, timeout=self.request_timeout)
                                logger.info(f"🔁 Fallback DELETE status for {mid}: {getattr(resp2,'status_code',None)}")
                                if getattr(resp2, 'status_code', None) in [200,204]:
                                    logger.info(f"✅ Fallback suppression réussie pour queue id={mid}")
                                    # proceed to trigger search
                                    try:
                                        success = self.trigger_missing_search(app_name, url, api_key)
                                    except Exception:
                                        success = False
                                    return {'status': 'ok', 'message': 'fallback deleted', 'details': {'queue_id': mid, 'triggered_search': success}}
                            except Exception as e:
                                logger.warning(f"⚠️ Fallback DELETE failed for queue id={mid}: {e}")

                    # If no matches or fallback failed, return original error
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lors du fallback de recherche dans la queue: {e}")

                return {'status': 'error', 'message': msg}

            logger.info(f"🚫 {app_name} release {download_id} blocklisted and removed")

            # Verify removal by re-querying the queue for the given download_id
            try:
                queue_after = self.get_queue(app_name, url, api_key)
                logger.debug(f"Vérification suppression: queue_after length={len(queue_after)}")

                def _matches(x):
                    try:
                        xid = x.get('id')
                        xdid = x.get('downloadId') or x.get('downloadid') or x.get('DownloadId')
                        # Normalize to strings lower-case for robust compare
                        cand = str(download_id).lower() if download_id is not None else None
                        if xid is not None and cand is not None and str(xid).lower() == cand:
                            return True
                        if xdid is not None and cand is not None and str(xdid).lower() == cand:
                            return True
                        return False
                    except Exception:
                        return False

                matching = [x for x in queue_after if _matches(x)]
                if matching:
                    logger.warning(f"⚠️ Vérification suppression: download_id={download_id} toujours présent dans la queue après suppression - matches={len(matching)}")
                    # Log minimal info about matches to help debugging
                    for m in matching[:5]:
                        try:
                            logger.warning(f"   match: id={m.get('id')} downloadId={m.get('downloadId')} title={m.get('title')}")
                        except Exception:
                            pass
                else:
                    logger.info(f"✅ Vérification suppression: download_id={download_id} absent de la queue")
            except Exception as e:
                logger.warning(f"⚠️ Impossible vérifier suppression pour download_id={download_id}: {e}")

            # Lancer une recherche pour les manqués (hook ou fallback)
            try:
                success = self.trigger_missing_search(app_name, url, api_key)
                if success:
                    msg = f"Blocked {download_id} and triggered missing search"
                    logger.info(f"🔍 {app_name} {msg}")
                    return {'status': 'ok', 'message': msg}
                else:
                    msg = f"Blocked {download_id} but trigger_missing_search failed"
                    logger.warning(f"🔍 {app_name} {msg}")
                    return {'status': 'ok', 'message': msg}
            except Exception as e:
                logger.exception(f"{app_name} exception when triggering search: {e}")
                return {'status': 'ok', 'message': f"Blocked {download_id} but search error: {e}"}

        except requests.exceptions.RequestException as e:
            logger.exception(f"❌ {app_name} exception blocklist: {e}")
            return {'status': 'error', 'message': f'exception:{e}'}
    
    def trigger_missing_search(self, app_name: str, url: str, api_key: str) -> bool:
        """Lance une recherche pour les éléments manqués"""
        try:
            endpoint = "wantedmissing" if app_name.lower() == "sonarr" else "wanted/missing"

            cmd_names = ['MissingEpisodeSearch'] if app_name.lower() == 'sonarr' else ['MissingMovieSearch', 'MissingMoviesSearch']

            for cmd in cmd_names:
                try:
                    response = self.session.post(
                        f"{url}/api/v3/command",
                        headers={'X-Api-Key': api_key},
                        json={'name': cmd},
                        timeout=self.request_timeout
                    )

                    # Log body for diagnostics on non-success
                    if response.status_code in [200, 201]:
                        logger.info(f"✅ {app_name} recherche manqués lancée (command={cmd})")
                        return True
                    else:
                        body = None
                        try:
                            body = response.text
                        except Exception:
                            try:
                                body = response.content.decode('utf-8', errors='replace')
                            except Exception:
                                body = '<unreadable body>'
                        logger.error(f"❌ {app_name} erreur recherche manqués (command={cmd}): {response.status_code} body:{body}")
                        # try next candidate
                except requests.exceptions.RequestException as e:
                    logger.warning(f"⚠️ {app_name} exception lors trigger_missing_search (command={cmd}): {e}")

            # All candidates failed
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
                params={'removeFromClient': 'true', 'blocklist': 'false'},
                timeout=self.request_timeout
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

    def perform_item_action(self, app_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to perform the same item action used by the web UI.

        This centralizes the logic so both the API endpoint and automatic
        handlers use identical behaviour (download id extraction, config lookup,
        call to blocklist_and_search, normalized return shape).
        """
        try:
            # Determine config
            if app_name.lower().startswith('sonarr'):
                cfg = self.get_sonarr_config()
            else:
                cfg = self.get_radarr_config()

            if not cfg:
                return {'success': False, 'message': 'configuration missing'}

            download_id = item.get('id') or item.get('downloadId') or item.get('releaseId') or item.get('DownloadId')
            if not download_id:
                return {'success': False, 'message': 'download id not found in item'}

            result = self.blocklist_and_search(app_name, cfg['url'], cfg['api_key'], download_id)
            if isinstance(result, dict):
                success = result.get('status') == 'ok'
                message = result.get('message')
            else:
                success = bool(result)
                message = None

            return {'success': success, 'message': message or ('action executed' if success else 'action failed'), 'raw': result}

        except Exception as e:
            logger.exception(f"perform_item_action failed: {e}")
            return {'success': False, 'message': str(e)}
    
    def is_download_failed(self, item: Dict[str, Any]) -> bool:
        """
        Détection complète des erreurs dans la queue Sonarr/Radarr
        Basé sur les tests API réels pour détecter tous les types d'erreurs
        """
        title = item.get('title', 'Inconnu')
        
        # 1. Vérifier trackedDownloadStatus = "warning" (état d'erreur principal)
        tracked_status = item.get('trackedDownloadStatus', '')
        if tracked_status == 'warning':
            logger.debug(f"🚨 Erreur détectée via trackedDownloadStatus=warning: {title}")
            return True
        
        # 2. Vérifier trackedDownloadState = "importBlocked" (import bloqué)
        tracked_state = item.get('trackedDownloadState', '')
        if tracked_state == 'importBlocked':
            logger.debug(f"🚨 Erreur détectée via trackedDownloadState=importBlocked: {title}")
            return True
        
        # 3. Vérifier présence d'errorMessage (message d'erreur explicite)
        error_message = item.get('errorMessage', '')
        if error_message and error_message.strip():
            logger.debug(f"🚨 Erreur détectée via errorMessage: {title} - {error_message}")
            # Détection spécifique pour qBittorrent
            if isinstance(error_message, str) and 'qBittorrent is reporting an error' in error_message:
                logger.debug(f"🚨 Erreur qBittorrent détectée: {title} - {error_message}")
                return True
            return True
        
        # 4. Vérifier status = "failed" (échec explicite)
        status = item.get('status', '')
        if status == 'failed':
            logger.debug(f"🚨 Erreur détectée via status=failed: {title}")
            return True
        
        # 5. Détections supplémentaires pour robustesse
        # Vérifier si statusMessages contient des erreurs
        status_messages = item.get('statusMessages', [])
        if status_messages:
            for msg in status_messages:
                if isinstance(msg, dict):
                    msg_title = msg.get('title', '').lower()
                    # Détecter aussi le message qBittorrent explicite
                    if 'qbittorrent' in msg_title or any(keyword in msg_title for keyword in ['error', 'failed', 'blocked', 'unable']):
                        logger.debug(f"🚨 Erreur détectée via statusMessages: {title} - {msg_title}")
                        return True
        
        # Aucune erreur détectée
        return False
    
    def process_application(self, app_name: str, config: Dict[str, str]) -> int:
        """
        Traite une application (Sonarr/Radarr) avec le gestionnaire multi-erreurs
        
        Args:
            app_name: Nom de l'application (Sonarr/Radarr)
            config: Configuration avec url et api_key
            
        Returns:
            int: Nombre d'éléments traités
        """
        url = config['url']
        api_key = config['api_key']
        
        # Vérifier la connectivité
        if not self.test_connection(app_name, url, api_key):
            logger.error(f"❌ {app_name} non accessible, passage au suivant")
            return 0
        
        # Récupérer la queue
        queue = self.get_queue(app_name, url, api_key)
        if not queue:
            logger.info(f"✅ {app_name} queue vide")
            return 0
        
        processed_items = 0
        error_summary = {}
        
        logger.info(f"� {app_name} analyse de {len(queue)} éléments")
        
        # Analyser chaque élément de la queue
        # Injecter le nom de l'application dans chaque item pour que les handlers
        # d'actions sachent sur quelle application (Sonarr/Radarr) opérer.
        for item in queue:
            try:
                # Préserver si déjà présent
                if not item.get('app_name'):
                    item['app_name'] = app_name
            except Exception:
                # Si item n'est pas un dict modifiable, continuer
                pass
            # Détecter le type d'erreur
            error_type = self.error_types_manager.detect_error_type(item)
            
            if error_type:
                # Vérifier si l'erreur doit être traitée
                if self.error_types_manager.should_process_error(error_type, item):
                    title = item.get('title', 'Inconnu')
                    download_id = item.get('id')
                    
                    logger.warning(f"� {app_name} erreur détectée [{error_type}]: {title}")
                    
                    # Traiter l'erreur selon sa configuration
                    # For automatic processing, skip action delays so behavior matches manual trigger
                    result = self.error_types_manager.process_error(error_type, item, self, skip_action_delays=True)
                    
                    if result.get("success", False):
                        processed_items += 1
                        actions_count = result.get("actions_executed", 0)
                        logger.info(f"✅ {app_name} correction appliquée [{error_type}]: {title} ({actions_count} actions)")
                        
                        # Comptabiliser par type d'erreur
                        if error_type not in error_summary:
                            error_summary[error_type] = 0
                        error_summary[error_type] += 1
                    else:
                        logger.error(f"❌ {app_name} échec correction [{error_type}]: {title}")
                else:
                    logger.debug(f"🚫 {app_name} erreur ignorée [{error_type}]: conditions non remplies")
        
        # Afficher le résumé
        if processed_items > 0:
            logger.info(f"🔧 {app_name} {processed_items} éléments corrigés:")
            for error_type, count in error_summary.items():
                logger.info(f"  • {error_type}: {count} corrections")
            
            # Lancer une recherche pour les manqués après corrections
            self.trigger_missing_search(app_name, url, api_key)
        else:
            logger.info(f"✅ {app_name} aucune erreur nécessitant correction")
        
        return processed_items
    
    def run_cycle(self) -> Dict[str, int]:
        """
        Exécute un cycle complet de surveillance
        
        Returns:
            Dict[str, int]: Statistiques du cycle (app_name -> nb_corrections)
        """
        # Prevent concurrent run_cycle executions
        acquired = self._run_lock.acquire(blocking=False)
        if not acquired:
            logger.info("⚠️ Un autre cycle est en cours, cycle actuel ignoré")
            return {}

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
        # release lock
        try:
            return results
        finally:
            try:
                self._run_lock.release()
            except RuntimeError:
                pass
    
    def start_monitoring(self, interval: int = 30) -> bool:
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
                    # attendre un peu avant de reprendre en cas d'erreur
                    time.sleep(30)

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
                'errors_detected': 0,
                'error_types_detected': {}
            }
        
        # Analyse des statuts et types d'erreurs
        status_count = {}
        error_items = []
        error_types_count = {}
        
        for item in queue:
            status = item.get('status', 'unknown')
            status_count[status] = status_count.get(status, 0) + 1
            
            # Détecter le type d'erreur avec le nouveau gestionnaire
            error_type = self.error_types_manager.detect_error_type(item)
            
            if error_type:
                # Comptabiliser les types d'erreurs
                if error_type not in error_types_count:
                    error_types_count[error_type] = 0
                error_types_count[error_type] += 1
                
                error_items.append({
                    'id': item.get('id'),
                    'title': item.get('title', 'Inconnu'),
                    'status': status,
                    'errorMessage': item.get('errorMessage', ''),
                    'errorType': error_type,
                    'canAutoCorrect': self.error_types_manager.should_process_error(error_type, item)
                })
        
        result = {
            'total_items': len(queue),
            'status_breakdown': status_count,
            'error_items': error_items,
            'errors_detected': len(error_items),
            'error_types_detected': error_types_count
        }
        
        logger.info(f"📊 {display_name} DIAGNOSTIC: {len(queue)} éléments, {len(error_items)} erreurs")
        if error_types_count:
            logger.info(f"   Types d'erreurs: {', '.join([f'{t}({c})' for t, c in error_types_count.items()])}")
        
        return result
    
    # API pour la gestion des types d'erreurs
    
    def get_error_types_config(self) -> Dict[str, Any]:
        """Retourne la configuration des types d'erreurs"""
        return self.error_types_manager.get_error_types_config()
    
    def update_error_type_config(self, error_type_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Met à jour la configuration d'un type d'erreur"""
        return self.error_types_manager.update_error_type_config(error_type_name, config_data)
    
    def create_error_type(self, error_type_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un nouveau type d'erreur"""
        return self.error_types_manager.create_error_type(error_type_name, config_data)
    
    def delete_error_type(self, error_type_name: str) -> Dict[str, Any]:
        """Supprime un type d'erreur"""
        return self.error_types_manager.delete_error_type(error_type_name)
    
    def get_available_actions(self) -> List[str]:
        """Retourne la liste des actions disponibles"""
        return self.error_types_manager.get_available_actions()
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques de détection"""
        return self.error_types_manager.get_detection_statistics()
    
    def test_error_detection(self, test_item: Dict[str, Any]) -> Dict[str, Any]:
        """Teste la détection d'erreur sur un élément donné"""
        error_type = self.error_types_manager.detect_error_type(test_item)
        
        result = {
            "item": test_item,
            "detected_error_type": error_type,
            "would_process": False,
            "actions_that_would_run": []
        }
        
        if error_type:
            result["would_process"] = self.error_types_manager.should_process_error(error_type, test_item)
            
            if result["would_process"] and error_type in self.error_types_manager.error_types:
                error_config = self.error_types_manager.error_types[error_type]
                result["actions_that_would_run"] = [
                    action.name for action in error_config.actions if action.enabled
                ]
        
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
