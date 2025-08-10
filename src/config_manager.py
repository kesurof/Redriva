#!/usr/bin/env python3
"""
Configuration Manager avec setup web interactif
Gère automatiquement les environnements dev/local et SSDV2/Docker
"""

import os
import json
import logging
import base64
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestionnaire de configuration avec setup web interactif"""
    
    def __init__(self):
        self.is_docker = self._detect_docker()
        self.config_path = self._get_config_path()
        self.config = self._load_config()
        
    def _get_config_path(self) -> Path:
        """Détermine le chemin du fichier de configuration"""
        if self.is_docker:
            return Path("/app/config/config.json")
        else:
            return Path(__file__).parent.parent / "config" / "config.json"
    
    def _detect_docker(self) -> bool:
        """Détecte si on est dans Docker/SSDV2"""
        return (
            os.path.exists('/.dockerenv') or
            os.path.exists('/app') or
            os.environ.get('DOCKER') == 'true' or
            os.environ.get('PUID') is not None
        )
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier JSON"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"✅ Configuration chargée depuis {self.config_path}")
                    return config
            else:
                # Essayer de créer depuis le fichier exemple
                example_path = self.config_path.parent / "config.example.json"
                if example_path.exists():
                    with open(example_path, 'r', encoding='utf-8') as f:
                        default_config = json.load(f)
                    logger.info(f"✅ Configuration créée depuis {example_path}")
                else:
                    # Fallback vers la configuration par défaut
                    default_config = self._get_default_config()
                    logger.info("✅ Configuration par défaut créée")
                
                self._save_config(default_config)
                return default_config
        except Exception as e:
            logger.error(f"❌ Erreur chargement config : {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut pour premier démarrage"""
        return {
            "version": "2.0",
            "setup_completed": False,
            "realdebrid": {
                "token": "",
                "api_limit": 100,
                "max_concurrent": 50,
                "batch_size": 250
            },
            "sonarr": {
                "url": "",
                "api_key": "",
                "enabled": False
            },
            "radarr": {
                "url": "",
                "api_key": "",
                "enabled": False
            },
            "app": {
                "sync_interval": 3600,
                "log_level": "INFO",
                "flask_debug": False
            },
            "flask": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False
            }
        }
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration"""
        try:
            # Créer le répertoire parent si nécessaire
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.config = config  # Mettre à jour l'instance
            logger.info(f"✅ Configuration sauvegardée : {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde config : {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Récupère une valeur de configuration"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    # Nouvelles méthodes pour setup web interactif
    def is_setup_completed(self) -> bool:
        """Vérifie si le setup initial est terminé"""
        return self.config.get('setup_completed', False)
    
    def get_db_path(self) -> str:
        """Récupère le chemin de la base de données"""
        if self.is_docker:
            return '/app/data/redriva.db'
        else:
            return str(Path(__file__).parent.parent / 'data' / 'redriva.db')
    
    def get_media_path(self) -> str:
        """Récupère le chemin des médias"""
        if self.is_docker:
            return '/app/medias'
        else:
            return str(Path.home() / 'Medias')
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Configuration Flask"""
        return {
            'host': self.get('flask.host', '0.0.0.0'),
            'port': self.get('flask.port', 5000),
            'debug': self.get('flask.debug', False)
        }

    # Nouvelles méthodes pour setup web interactif
    def is_setup_completed(self) -> bool:
        """Vérifie si le setup initial est terminé"""
        return self.config.get('setup_completed', False)
    
    def needs_setup(self) -> bool:
        """Vérifie si l'application a besoin d'être configurée"""
        if not self.is_setup_completed():
            return True
        
        # Vérifier que le token est configuré
        token = self.config.get('realdebrid', {}).get('token', '')
        return not token or token == ''
    
    def get_setup_status(self) -> Dict[str, Any]:
        """Retourne le statut du setup"""
        config = self.config
        rd_config = config.get('realdebrid', {})
        
        return {
            'setup_completed': config.get('setup_completed', False),
            'has_token': bool(rd_config.get('token')),
            'has_sonarr': bool(config.get('sonarr', {}).get('url')),
            'has_radarr': bool(config.get('radarr', {}).get('url')),
            'needs_setup': self.needs_setup()
        }
    
    def save_setup_config(self, setup_data: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration du setup initial"""
        try:
            # Mettre à jour la configuration Real-Debrid
            if 'rd_token' in setup_data and setup_data['rd_token']:
                if 'realdebrid' not in self.config:
                    self.config['realdebrid'] = {}
                self.config['realdebrid']['token'] = setup_data['rd_token']
            
            # Configuration Sonarr (optionnelle)
            if 'sonarr_url' in setup_data or 'sonarr_api_key' in setup_data:
                if 'sonarr' not in self.config:
                    self.config['sonarr'] = {}
                
                if 'sonarr_url' in setup_data:
                    self.config['sonarr']['url'] = setup_data['sonarr_url']
                    self.config['sonarr']['enabled'] = bool(setup_data['sonarr_url'])
                
                if 'sonarr_api_key' in setup_data:
                    self.config['sonarr']['api_key'] = setup_data['sonarr_api_key']
            
            # Configuration Radarr (optionnelle)
            if 'radarr_url' in setup_data or 'radarr_api_key' in setup_data:
                if 'radarr' not in self.config:
                    self.config['radarr'] = {}
                
                if 'radarr_url' in setup_data:
                    self.config['radarr']['url'] = setup_data['radarr_url']
                    self.config['radarr']['enabled'] = bool(setup_data['radarr_url'])
                
                if 'radarr_api_key' in setup_data:
                    self.config['radarr']['api_key'] = setup_data['radarr_api_key']
            
            # Marquer le setup comme terminé
            self.config['setup_completed'] = True
            
            # Sauvegarder
            return self._save_config(self.config)
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde setup : {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_token(self) -> Optional[str]:
        """Récupère le token Real-Debrid depuis la configuration centralisée"""
        return self.config.get('realdebrid', {}).get('token')
    
    def update_config(self, key: str, value: Any) -> bool:
        """Met à jour une valeur de configuration"""
        try:
            keys = key.split('.')
            config = self.config
            
            # Naviguer jusqu'au niveau parent
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # Mettre à jour la valeur
            config[keys[-1]] = value
            
            # Sauvegarder
            return self._save_config(self.config)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour config : {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Réinitialise la configuration avec les valeurs par défaut"""
        try:
            default_config = self._get_default_config()
            return self._save_config(default_config)
        except Exception as e:
            logger.error(f"❌ Erreur réinitialisation config : {e}")
            return False
    
    def get_full_config(self) -> Dict[str, Any]:
        """Retourne la configuration complète (sans tokens sensibles)"""
        config_copy = self.config.copy()
        # Masquer le token pour des raisons de sécurité
        if 'realdebrid' in config_copy and 'token' in config_copy['realdebrid']:
            config_copy['realdebrid'] = config_copy['realdebrid'].copy()
            config_copy['realdebrid']['token'] = ''
        return config_copy
    
    def set_full_config(self, new_config: Dict[str, Any]) -> bool:
        """Met à jour la configuration complète"""
        try:
            return self._save_config(new_config)
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour config complète : {e}")
            return False

# Instance globale
_config = None

def get_config() -> ConfigManager:
    """Récupère l'instance de configuration"""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config

# Fonctions de compatibilité
def load_token() -> Optional[str]:
    return get_config().get_token()

def get_database_path() -> str:
    return get_config().get_db_path()

def get_media_path() -> str:
    return get_config().get_media_path()
