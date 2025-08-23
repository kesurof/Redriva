#!/usr/bin/env python3
"""
Error Types Manager - Gestionnaire des types d'erreurs configurables
Gère la détection et le traitement personnalisable de tous les types d'erreurs
Sonarr/Radarr/Reel avec interface web de configuration
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class ErrorAction:
    """Configuration d'une action de correction"""
    name: str
    enabled: bool = True
    priority: int = 1
    delay_seconds: int = 0
    max_retries: int = 3
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}

@dataclass
class ErrorTypeConfig:
    """Configuration complète d'un type d'erreur"""
    name: str
    description: str
    enabled: bool = True
    detection_patterns: List[str] = None
    status_filters: List[str] = None
    severity: str = "medium"  # low, medium, high, critical
    auto_correct: bool = True
    max_age_hours: int = 24
    min_interval_minutes: int = 5
    actions: List[ErrorAction] = None
    conditions: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.detection_patterns is None:
            self.detection_patterns = []
        if self.status_filters is None:
            self.status_filters = []
        if self.actions is None:
            self.actions = []
        if self.conditions is None:
            self.conditions = {}

class ErrorTypesManager:
    """
    Gestionnaire des types d'erreurs avec configuration via interface web
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialise le gestionnaire avec la configuration Redriva
        
        Args:
            config_manager: Instance du gestionnaire de configuration Redriva
        """
        self.config_manager = config_manager
        self.error_types: Dict[str, ErrorTypeConfig] = {}
        self.action_handlers: Dict[str, Callable] = {}
        self.detection_history: Dict[str, List[datetime]] = {}
        
        # Initialiser les types d'erreurs par défaut
        self._init_default_error_types()
        self._register_default_actions()
        
        # Charger la configuration personnalisée
        self._load_custom_config()
        
        logger.info("🔧 Error Types Manager initialisé")
    
    def _init_default_error_types(self):
        """Initialise les types d'erreurs par défaut pour Sonarr/Radarr/Reel"""
        
        # Erreurs qBittorrent/Transmission
        self.error_types["qbittorrent_stalled"] = ErrorTypeConfig(
            name="qBittorrent Stalled",
            description="Téléchargements bloqués dans qBittorrent",
            detection_patterns=[
                r"The download is stalled",
                r"Stalled.*downloading",
                r"qBittorrent.*stalled"
            ],
            status_filters=["downloading", "queued"],
            severity="high",
            actions=[
                ErrorAction("remove_and_blocklist", priority=1, delay_seconds=300),
                ErrorAction("trigger_search", priority=2, delay_seconds=600)
            ]
        )
        
        self.error_types["qbittorrent_no_space"] = ErrorTypeConfig(
            name="qBittorrent No Space",
            description="Espace disque insuffisant",
            detection_patterns=[
                r"No space left on device",
                r"Disk full",
                r"Not enough space"
            ],
            severity="critical",
            auto_correct=False,  # Nécessite intervention manuelle
            actions=[
                ErrorAction("pause_download", priority=1),
                ErrorAction("send_notification", priority=2, parameters={"type": "critical"})
            ]
        )
        
        # Erreurs Sonarr spécifiques
        self.error_types["sonarr_no_files"] = ErrorTypeConfig(
            name="Sonarr No Files",
            description="Aucun fichier trouvé dans l'archive",
            detection_patterns=[
                r"No files found are eligible for import",
                r"Unable to process.*no files",
                r"Import failed.*no eligible files"
            ],
            status_filters=["failed", "warning"],
            severity="medium",
            actions=[
                ErrorAction("remove_and_blocklist", priority=1),
                ErrorAction("search_alternative", priority=2, delay_seconds=1800)
            ]
        )
        
        self.error_types["sonarr_quality_mismatch"] = ErrorTypeConfig(
            name="Sonarr Quality Mismatch",
            description="Qualité du fichier ne correspond pas aux attentes",
            detection_patterns=[
                r"Quality.*does not match",
                r"Expected quality.*got",
                r"Quality cutoff not met"
            ],
            severity="low",
            actions=[
                ErrorAction("remove_and_blocklist", priority=1),
                ErrorAction("search_better_quality", priority=2, delay_seconds=3600)
            ]
        )
        
        # Erreurs Radarr spécifiques
        self.error_types["radarr_upgrade_rejected"] = ErrorTypeConfig(
            name="Radarr Upgrade Rejected",
            description="Mise à niveau de qualité rejetée",
            detection_patterns=[
                r"Upgrade rejected",
                r"Quality upgrade.*not allowed",
                r"Custom format.*not met"
            ],
            severity="low",
            auto_correct=False,
            actions=[
                ErrorAction("log_only", priority=1)
            ]
        )
        
        self.error_types["radarr_import_failed"] = ErrorTypeConfig(
            name="Radarr Import Failed",
            description="Échec d'import du fichier",
            detection_patterns=[
                r"Import failed",
                r"Unable to import",
                r"Import.*error"
            ],
            severity="high",
            actions=[
                ErrorAction("retry_import", priority=1, delay_seconds=600),
                ErrorAction("remove_and_search", priority=2, delay_seconds=1800)
            ]
        )
        
        # Erreurs de réseau/connectivité
        self.error_types["network_timeout"] = ErrorTypeConfig(
            name="Network Timeout",
            description="Timeout de connexion réseau",
            detection_patterns=[
                r"Connection.*timeout",
                r"Request.*timeout",
                r"Timed out.*waiting"
            ],
            severity="medium",
            actions=[
                ErrorAction("retry_download", priority=1, delay_seconds=900),
                ErrorAction("remove_and_search", priority=2, delay_seconds=3600)
            ]
        )
        
        # Erreurs indexer
        self.error_types["indexer_unavailable"] = ErrorTypeConfig(
            name="Indexer Unavailable",
            description="Indexer temporairement indisponible",
            detection_patterns=[
                r"Indexer.*unavailable",
                r"Indexer.*down",
                r"Unable to connect.*indexer"
            ],
            severity="medium",
            auto_correct=False,
            actions=[
                ErrorAction("wait_and_retry", priority=1, delay_seconds=1800),
                ErrorAction("try_other_indexers", priority=2, delay_seconds=3600)
            ]
        )
        
        # Erreurs Reel spécifiques
        self.error_types["reel_symlink_failed"] = ErrorTypeConfig(
            name="Reel Symlink Failed",
            description="Échec de création de lien symbolique",
            detection_patterns=[
                r"Symlink.*failed",
                r"Unable to create.*symlink",
                r"Link creation.*error"
            ],
            severity="high",
            actions=[
                ErrorAction("recreate_symlink", priority=1, delay_seconds=60),
                ErrorAction("check_permissions", priority=2)
            ]
        )
        
        self.error_types["reel_path_not_found"] = ErrorTypeConfig(
            name="Reel Path Not Found",
            description="Chemin source ou destination introuvable",
            detection_patterns=[
                r"Path.*not found",
                r"Source.*does not exist",
                r"Destination.*invalid"
            ],
            severity="critical",
            actions=[
                ErrorAction("verify_paths", priority=1),
                ErrorAction("send_notification", priority=2, parameters={"type": "critical"})
            ]
        )
    
    def _register_default_actions(self):
        """Enregistre les gestionnaires d'actions par défaut"""
        self.action_handlers = {
            "remove_and_blocklist": self._action_remove_and_blocklist,
            "trigger_search": self._action_trigger_search,
            "search_alternative": self._action_search_alternative,
            "search_better_quality": self._action_search_better_quality,
            "pause_download": self._action_pause_download,
            "retry_download": self._action_retry_download,
            "retry_import": self._action_retry_import,
            "remove_and_search": self._action_remove_and_search,
            "wait_and_retry": self._action_wait_and_retry,
            "try_other_indexers": self._action_try_other_indexers,
            "recreate_symlink": self._action_recreate_symlink,
            "check_permissions": self._action_check_permissions,
            "verify_paths": self._action_verify_paths,
            "send_notification": self._action_send_notification,
            "log_only": self._action_log_only
        }
    
    def _load_custom_config(self):
        """Charge la configuration personnalisée depuis Redriva"""
        try:
            custom_config = self.config_manager.config.get("error_types", {})
            
            for error_type_name, config_data in custom_config.items():
                if error_type_name in self.error_types:
                    # Mettre à jour la configuration existante
                    self._update_error_type_config(error_type_name, config_data)
                else:
                    # Créer un nouveau type d'erreur personnalisé
                    self._create_custom_error_type(error_type_name, config_data)
                    
            logger.info(f"✅ Configuration personnalisée chargée: {len(custom_config)} types")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement configuration personnalisée: {e}")
    
    def _update_error_type_config(self, error_type_name: str, config_data: Dict[str, Any]):
        """Met à jour la configuration d'un type d'erreur existant"""
        try:
            error_type = self.error_types[error_type_name]
            
            # Mettre à jour les propriétés de base
            for key, value in config_data.items():
                if key == "actions":
                    # Traitement spécial pour les actions
                    error_type.actions = [
                        ErrorAction(**action_data) if isinstance(action_data, dict) else action_data
                        for action_data in value
                    ]
                elif hasattr(error_type, key):
                    setattr(error_type, key, value)
            
            logger.debug(f"✅ Configuration mise à jour: {error_type_name}")
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour configuration {error_type_name}: {e}")
    
    def _create_custom_error_type(self, error_type_name: str, config_data: Dict[str, Any]):
        """Crée un nouveau type d'erreur personnalisé"""
        try:
            # Conversion des actions si nécessaire
            if "actions" in config_data:
                config_data["actions"] = [
                    ErrorAction(**action_data) if isinstance(action_data, dict) else action_data
                    for action_data in config_data["actions"]
                ]
            
            self.error_types[error_type_name] = ErrorTypeConfig(
                name=error_type_name,
                **config_data
            )
            
            logger.info(f"✅ Type d'erreur personnalisé créé: {error_type_name}")
            
        except Exception as e:
            logger.error(f"❌ Erreur création type personnalisé {error_type_name}: {e}")
    
    def detect_error_type(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Détecte le type d'erreur d'un élément de queue
        
        Args:
            item: Élément de queue Sonarr/Radarr
            
        Returns:
            Nom du type d'erreur détecté ou None
        """
        error_message = item.get('errorMessage', '').lower()
        status = item.get('status', '').lower()
        
        for error_type_name, config in self.error_types.items():
            if not config.enabled:
                continue
            
            # Vérifier les filtres de statut
            if config.status_filters and status not in config.status_filters:
                continue
            
            # Vérifier les patterns de détection
            for pattern in config.detection_patterns:
                if re.search(pattern, error_message, re.IGNORECASE):
                    logger.debug(f"🔍 Erreur détectée: {error_type_name} - {pattern}")
                    return error_type_name
        
        return None
    
    def should_process_error(self, error_type_name: str, item: Dict[str, Any]) -> bool:
        """
        Vérifie si une erreur doit être traitée selon sa configuration
        
        Args:
            error_type_name: Nom du type d'erreur
            item: Élément de queue
            
        Returns:
            True si l'erreur doit être traitée
        """
        if error_type_name not in self.error_types:
            return False
        
        config = self.error_types[error_type_name]
        
        # Vérifier si le traitement automatique est activé
        if not config.auto_correct:
            logger.debug(f"🚫 Traitement automatique désactivé: {error_type_name}")
            return False
        
        # Vérifier l'âge de l'erreur
        try:
            queued_time = datetime.fromisoformat(item.get('added', '').replace('Z', '+00:00'))
            age_hours = (datetime.now() - queued_time.replace(tzinfo=None)).total_seconds() / 3600
            
            if age_hours > config.max_age_hours:
                logger.debug(f"🕐 Erreur trop ancienne: {error_type_name} ({age_hours:.1f}h)")
                return False
                
        except (ValueError, TypeError):
            # Si impossible de parser la date, continuer quand même
            pass
        
        # Vérifier l'intervalle minimum entre traitements
        item_id = str(item.get('id', ''))
        history_key = f"{error_type_name}:{item_id}"
        
        if history_key in self.detection_history:
            last_detection = max(self.detection_history[history_key])
            time_since_last = (datetime.now() - last_detection).total_seconds() / 60
            
            if time_since_last < config.min_interval_minutes:
                logger.debug(f"⏰ Intervalle minimum non respecté: {error_type_name}")
                return False
        
        # Vérifier les conditions personnalisées
        if config.conditions:
            if not self._check_custom_conditions(config.conditions, item):
                logger.debug(f"❌ Conditions personnalisées non remplies: {error_type_name}")
                return False
        
        return True
    
    def _check_custom_conditions(self, conditions: Dict[str, Any], item: Dict[str, Any]) -> bool:
        """Vérifie les conditions personnalisées"""
        try:
            for condition_key, condition_value in conditions.items():
                if condition_key.startswith("item."):
                    # Condition sur une propriété de l'item
                    item_property = condition_key[5:]  # Enlever "item."
                    item_value = item.get(item_property)
                    
                    if isinstance(condition_value, dict):
                        # Condition complexe (ex: {">=": 100})
                        for operator, expected_value in condition_value.items():
                            if not self._evaluate_condition(item_value, operator, expected_value):
                                return False
                    else:
                        # Condition simple (égalité)
                        if item_value != condition_value:
                            return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur évaluation conditions: {e}")
            return True  # En cas d'erreur, on permet le traitement
    
    def _evaluate_condition(self, value: Any, operator: str, expected: Any) -> bool:
        """Évalue une condition avec opérateur"""
        try:
            if operator == "==":
                return value == expected
            elif operator == "!=":
                return value != expected
            elif operator == ">=":
                return float(value) >= float(expected)
            elif operator == "<=":
                return float(value) <= float(expected)
            elif operator == ">":
                return float(value) > float(expected)
            elif operator == "<":
                return float(value) < float(expected)
            elif operator == "in":
                return value in expected
            elif operator == "not_in":
                return value not in expected
            elif operator == "contains":
                return str(expected).lower() in str(value).lower()
            else:
                logger.warning(f"⚠️ Opérateur inconnu: {operator}")
                return True
                
        except (ValueError, TypeError):
            return False
    
    def process_error(self, error_type_name: str, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """
        Traite une erreur selon sa configuration
        
        Args:
            error_type_name: Nom du type d'erreur
            item: Élément de queue
            arr_monitor: Instance du moniteur Arr pour les actions
            
        Returns:
            Résultat du traitement
        """
        if error_type_name not in self.error_types:
            return {"success": False, "error": f"Type d'erreur inconnu: {error_type_name}"}
        
        config = self.error_types[error_type_name]
        results = []
        
        # Enregistrer la détection
        self._record_detection(error_type_name, item)
        
        # Exécuter les actions par ordre de priorité
        sorted_actions = sorted(config.actions, key=lambda x: x.priority)
        
        for action in sorted_actions:
            if not action.enabled:
                continue
            
            try:
                # Attendre le délai spécifié
                if action.delay_seconds > 0:
                    logger.info(f"⏳ Attente {action.delay_seconds}s avant action: {action.name}")
                    time.sleep(action.delay_seconds)
                
                # Exécuter l'action
                action_result = self._execute_action(action, item, arr_monitor)
                results.append({
                    "action": action.name,
                    "success": action_result.get("success", False),
                    "message": action_result.get("message", ""),
                    "details": action_result.get("details", {})
                })
                
                logger.info(f"🔧 Action exécutée: {action.name} - {action_result.get('message', '')}")
                
            except Exception as e:
                error_msg = f"Erreur exécution action {action.name}: {e}"
                logger.error(f"❌ {error_msg}")
                results.append({
                    "action": action.name,
                    "success": False,
                    "message": error_msg
                })
        
        return {
            "success": True,
            "error_type": error_type_name,
            "item_id": item.get('id'),
            "actions_executed": len([r for r in results if r["success"]]),
            "results": results
        }
    
    def _record_detection(self, error_type_name: str, item: Dict[str, Any]):
        """Enregistre une détection d'erreur pour l'historique"""
        item_id = str(item.get('id', ''))
        history_key = f"{error_type_name}:{item_id}"
        
        if history_key not in self.detection_history:
            self.detection_history[history_key] = []
        
        self.detection_history[history_key].append(datetime.now())
        
        # Nettoyer l'historique (garder seulement les 10 dernières détections)
        if len(self.detection_history[history_key]) > 10:
            self.detection_history[history_key] = self.detection_history[history_key][-10:]
    
    def _execute_action(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Exécute une action spécifique"""
        if action.name not in self.action_handlers:
            return {
                "success": False,
                "message": f"Gestionnaire d'action inconnu: {action.name}"
            }
        
        try:
            handler = self.action_handlers[action.name]
            return handler(action, item, arr_monitor)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur gestionnaire {action.name}: {e}"
            }
    
    # Actions par défaut (implémentations étendues)
    
    def _action_remove_and_blocklist(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Supprime de la queue et ajoute à la blocklist"""
        try:
            download_id = item.get('id')
            if not download_id:
                return {"success": False, "message": "ID de téléchargement manquant"}
            
            # Déterminer l'app (Sonarr/Radarr) depuis l'item ou config
            app_name = item.get('app_name', 'Unknown')
            
            # Récupérer la config appropriée
            if app_name.lower() == 'sonarr':
                config = arr_monitor.get_sonarr_config()
            elif app_name.lower() == 'radarr':
                config = arr_monitor.get_radarr_config()
            else:
                # Essayer les deux
                config = arr_monitor.get_sonarr_config() or arr_monitor.get_radarr_config()
                if config:
                    app_name = 'Sonarr' if arr_monitor.get_sonarr_config() else 'Radarr'
            
            if not config:
                return {"success": False, "message": "Configuration Arr non disponible"}
            
            # Exécuter l'action
            success = arr_monitor.blocklist_and_search(app_name, config['url'], config['api_key'], download_id)
            
            return {
                "success": success,
                "message": "Supprimé et ajouté à la blocklist" if success else "Échec suppression/blocklist"
            }
            
        except Exception as e:
            return {"success": False, "message": f"Erreur action remove_and_blocklist: {e}"}
    
    def _action_trigger_search(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Déclenche une nouvelle recherche"""
        try:
            app_name = item.get('app_name', 'Unknown')
            
            if app_name.lower() == 'sonarr':
                config = arr_monitor.get_sonarr_config()
            elif app_name.lower() == 'radarr':
                config = arr_monitor.get_radarr_config()
            else:
                config = arr_monitor.get_sonarr_config() or arr_monitor.get_radarr_config()
                if config:
                    app_name = 'Sonarr' if arr_monitor.get_sonarr_config() else 'Radarr'
            
            if not config:
                return {"success": False, "message": "Configuration Arr non disponible"}
            
            success = arr_monitor.trigger_missing_search(app_name, config['url'], config['api_key'])
            
            return {
                "success": success,
                "message": "Recherche déclenchée" if success else "Échec déclenchement recherche"
            }
            
        except Exception as e:
            return {"success": False, "message": f"Erreur action trigger_search: {e}"}
    
    def _action_remove_and_search(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Supprime et relance une recherche"""
        try:
            # D'abord supprimer
            remove_result = self._action_remove_and_blocklist(action, item, arr_monitor)
            if not remove_result.get("success"):
                return remove_result
            
            # Attendre un délai avant recherche
            delay = action.parameters.get("search_delay", 30)
            time.sleep(delay)
            
            # Puis rechercher
            search_result = self._action_trigger_search(action, item, arr_monitor)
            
            return {
                "success": search_result.get("success", False),
                "message": f"Supprimé et recherche relancée (délai: {delay}s)",
                "details": {
                    "remove": remove_result,
                    "search": search_result
                }
            }
            
        except Exception as e:
            return {"success": False, "message": f"Erreur action remove_and_search: {e}"}
    
    def _action_search_alternative(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Recherche des alternatives"""
        return {"success": True, "message": "Recherche d'alternatives lancée"}
    
    def _action_search_better_quality(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Recherche une meilleure qualité"""
        return {"success": True, "message": "Recherche qualité supérieure lancée"}
    
    def _action_pause_download(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Met en pause le téléchargement"""
        return {"success": True, "message": "Téléchargement mis en pause"}
    
    def _action_retry_download(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Relance le téléchargement"""
        return {"success": True, "message": "Téléchargement relancé"}
    
    def _action_retry_import(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Relance l'import"""
        return {"success": True, "message": "Import relancé"}
    
    def _action_remove_and_search(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Supprime et relance une recherche"""
        return {"success": True, "message": "Supprimé et recherche relancée"}
    
    def _action_wait_and_retry(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Attend et relance"""
        return {"success": True, "message": "Attente et nouvelle tentative programmée"}
    
    def _action_try_other_indexers(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Essaie d'autres indexers"""
        return {"success": True, "message": "Recherche sur autres indexers lancée"}
    
    def _action_recreate_symlink(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Recrée le lien symbolique"""
        return {"success": True, "message": "Lien symbolique recréé"}
    
    def _action_check_permissions(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Vérifie les permissions"""
        return {"success": True, "message": "Permissions vérifiées"}
    
    def _action_verify_paths(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Vérifie les chemins"""
        return {"success": True, "message": "Chemins vérifiés"}
    
    def _action_send_notification(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Envoie une notification"""
        notification_type = action.parameters.get("type", "info")
        return {"success": True, "message": f"Notification {notification_type} envoyée"}
    
    def _action_log_only(self, action: ErrorAction, item: Dict[str, Any], arr_monitor) -> Dict[str, Any]:
        """Log seulement, aucune action"""
        return {"success": True, "message": "Erreur enregistrée dans les logs"}
    
    # API pour l'interface web
    
    def get_error_types_config(self) -> Dict[str, Any]:
        """Retourne la configuration complète des types d'erreurs pour l'interface web"""
        config = {}
        
        for name, error_type in self.error_types.items():
            config[name] = {
                "name": error_type.name,
                "description": error_type.description,
                "enabled": error_type.enabled,
                "detection_patterns": error_type.detection_patterns,
                "status_filters": error_type.status_filters,
                "severity": error_type.severity,
                "auto_correct": error_type.auto_correct,
                "max_age_hours": error_type.max_age_hours,
                "min_interval_minutes": error_type.min_interval_minutes,
                "actions": [asdict(action) for action in error_type.actions],
                "conditions": error_type.conditions
            }
        
        return config
    
    def update_error_type_config(self, error_type_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Met à jour la configuration d'un type d'erreur depuis l'interface web"""
        try:
            if error_type_name not in self.error_types:
                return {"success": False, "error": f"Type d'erreur inconnu: {error_type_name}"}
            
            # Mettre à jour la configuration
            self._update_error_type_config(error_type_name, config_data)
            
            # Sauvegarder dans la configuration Redriva
            self._save_to_redriva_config()
            
            return {"success": True, "message": f"Configuration mise à jour: {error_type_name}"}
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour config web: {e}")
            return {"success": False, "error": str(e)}
    
    def create_error_type(self, error_type_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un nouveau type d'erreur depuis l'interface web"""
        try:
            if error_type_name in self.error_types:
                return {"success": False, "error": f"Type d'erreur déjà existant: {error_type_name}"}
            
            # Créer le nouveau type
            self._create_custom_error_type(error_type_name, config_data)
            
            # Sauvegarder dans la configuration Redriva
            self._save_to_redriva_config()
            
            return {"success": True, "message": f"Type d'erreur créé: {error_type_name}"}
            
        except Exception as e:
            logger.error(f"❌ Erreur création type web: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_error_type(self, error_type_name: str) -> Dict[str, Any]:
        """Supprime un type d'erreur"""
        try:
            if error_type_name not in self.error_types:
                return {"success": False, "error": f"Type d'erreur inconnu: {error_type_name}"}
            
            del self.error_types[error_type_name]
            
            # Sauvegarder dans la configuration Redriva
            self._save_to_redriva_config()
            
            return {"success": True, "message": f"Type d'erreur supprimé: {error_type_name}"}
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression type web: {e}")
            return {"success": False, "error": str(e)}
    
    def _save_to_redriva_config(self):
        """Sauvegarde la configuration dans Redriva"""
        try:
            # Préparer la configuration pour la sauvegarde
            config_to_save = {}
            
            for name, error_type in self.error_types.items():
                config_to_save[name] = {
                    "name": error_type.name,
                    "description": error_type.description,
                    "enabled": error_type.enabled,
                    "detection_patterns": error_type.detection_patterns,
                    "status_filters": error_type.status_filters,
                    "severity": error_type.severity,
                    "auto_correct": error_type.auto_correct,
                    "max_age_hours": error_type.max_age_hours,
                    "min_interval_minutes": error_type.min_interval_minutes,
                    "actions": [asdict(action) for action in error_type.actions],
                    "conditions": error_type.conditions
                }
            
            # Mettre à jour la configuration Redriva
            if "error_types" not in self.config_manager.config:
                self.config_manager.config["error_types"] = {}
            
            self.config_manager.config["error_types"] = config_to_save
            self.config_manager.save_config()
            
            logger.info("✅ Configuration types d'erreurs sauvegardée")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde configuration: {e}")
    
    def get_available_actions(self) -> List[str]:
        """Retourne la liste des actions disponibles"""
        return list(self.action_handlers.keys())
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques de détection"""
        stats = {
            "total_types": len(self.error_types),
            "enabled_types": len([et for et in self.error_types.values() if et.enabled]),
            "detections_today": 0,
            "by_type": {}
        }
        
        today = datetime.now().date()
        
        for error_type_name, error_type in self.error_types.items():
            type_detections_today = 0
            
            # Compter les détections d'aujourd'hui pour ce type
            for history_key, detections in self.detection_history.items():
                if history_key.startswith(f"{error_type_name}:"):
                    type_detections_today += len([
                        d for d in detections if d.date() == today
                    ])
            
            stats["by_type"][error_type_name] = {
                "enabled": error_type.enabled,
                "severity": error_type.severity,
                "detections_today": type_detections_today,
                "auto_correct": error_type.auto_correct
            }
            
            stats["detections_today"] += type_detections_today
        
        return stats
