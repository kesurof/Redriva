#!/usr/bin/env python3
"""
Configuration Manager simplifié pour Redriva
Gère automatiquement les environnements dev/local et SSDV2/Docker
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestionnaire de configuration simplifié"""
    
    def __init__(self):
        self.is_docker = self._detect_docker()
        self.config = self._load_config()
    
    def _detect_docker(self) -> bool:
        """Détecte si on est dans Docker/SSDV2"""
        return (
            os.path.exists('/.dockerenv') or
            os.path.exists('/app') or
            os.environ.get('DOCKER') == 'true' or
            os.environ.get('PUID') is not None
        )
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration"""
        if self.is_docker:
            config_path = '/app/config/config.json'
        else:
            config_path = Path(__file__).parent.parent / 'config' / 'config.json'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Configuration par défaut utilisée: {e}")
            return {
                "realdebrid": {"api_url": "https://api.real-debrid.com/rest/1.0"},
                "flask": {"host": "0.0.0.0", "port": 5000},
                "logging": {"level": "INFO"}
            }
    
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
    
    def get_token(self) -> Optional[str]:
        """Récupère le token Real-Debrid"""
        # Priorité : variable d'environnement > fichier token
        token = os.environ.get('RD_TOKEN')
        if token and token != 'your_real_debrid_token_here':
            return token
        
        # Fichier token pour développement local
        if not self.is_docker:
            token_file = Path(__file__).parent.parent / 'data' / 'token'
            if token_file.exists():
                try:
                    return token_file.read_text().strip()
                except Exception:
                    pass
        
        return None
    
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
