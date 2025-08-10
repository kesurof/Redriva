#!/bin/bash

# Script d'entrée pour Redriva Docker
# Gère la configuration via variables d'environnement

echo "🚀 Démarrage de Redriva..."

# Vérifier et créer les répertoires nécessaires
echo "📁 Vérification des répertoires..."
mkdir -p /app/config /app/data /app/medias

# Vérifier les permissions et les corriger si nécessaire
if [ ! -w /app/config ]; then
    echo "⚠️ Correction des permissions /app/config"
    sudo chown -R $(id -u):$(id -g) /app/config 2>/dev/null || true
fi

if [ ! -w /app/data ]; then
    echo "⚠️ Correction des permissions /app/data"
    sudo chown -R $(id -u):$(id -g) /app/data 2>/dev/null || true
fi

# Créer le fichier de configuration depuis les variables d'environnement si elles sont définies
CONFIG_FILE="/app/config/config.json"
CONFIG_EXAMPLE="/app/config/config.example.json"

# S'assurer que le fichier exemple existe dans le répertoire config monté
if [ ! -f "$CONFIG_EXAMPLE" ]; then
    echo "📄 Copie du fichier exemple de configuration..."
    cat > "$CONFIG_EXAMPLE" << 'EOF'
{
  "token": "",
  "setup_completed": false,
  "auto_sync": true,
  "sync_interval": 300,
  "database_path": "/app/data/redriva.db",
  "sonarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "radarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "symlink": {
    "enabled": true,
    "media_path": "/app/medias",
    "workers": 4,
    "sonarr_enabled": false,
    "sonarr_url": "",
    "sonarr_api_key": "",
    "radarr_enabled": false,
    "radarr_url": "",
    "radarr_api_key": ""
  }
}
EOF
fi

if [ ! -f "$CONFIG_FILE" ] || [ "$RD_TOKEN" != "" ]; then
    echo "🔧 Configuration depuis les variables d'environnement..."
    
    # Copier le template par défaut
    if [ -f "$CONFIG_EXAMPLE" ]; then
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    else
        # Créer un fichier de configuration par défaut si le template n'existe pas
        cat > "$CONFIG_FILE" << 'EOF'
{
  "token": "",
  "setup_completed": false,
  "auto_sync": true,
  "sync_interval": 300,
  "database_path": "/app/data/redriva.db",
  "sonarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "radarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "symlink": {
    "enabled": true,
    "media_path": "/app/medias",
    "workers": 4,
    "sonarr_enabled": false,
    "sonarr_url": "",
    "sonarr_api_key": "",
    "radarr_enabled": false,
    "radarr_url": "",
    "radarr_api_key": ""
  }
}
EOF
    fi
    
    # Remplacer les valeurs si les variables d'environnement sont définies
    if [ "$RD_TOKEN" != "" ]; then
        echo "  ✅ Token Real-Debrid configuré"
        sed -i "s/\"token\": \"\"/\"token\": \"$RD_TOKEN\"/g" "$CONFIG_FILE"
        sed -i "s/\"setup_completed\": false/\"setup_completed\": true/g" "$CONFIG_FILE"
    fi
    
    if [ "$SONARR_URL" != "" ]; then
        echo "  ✅ Sonarr configuré: $SONARR_URL"
        # Utiliser Python pour une manipulation JSON plus sûre
        python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    config['sonarr']['url'] = '$SONARR_URL'
    config['sonarr']['enabled'] = True
    if 'symlink' in config:
        config['symlink']['sonarr_url'] = '$SONARR_URL'
        config['symlink']['sonarr_enabled'] = True
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
except Exception as e:
    print(f'Erreur configuration Sonarr: {e}')
"
    fi
    
    if [ "$SONARR_API_KEY" != "" ]; then
        echo "  ✅ Clé API Sonarr configurée"
        python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    config['sonarr']['api_key'] = '$SONARR_API_KEY'
    if 'symlink' in config:
        config['symlink']['sonarr_api_key'] = '$SONARR_API_KEY'
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
except Exception as e:
    print(f'Erreur configuration Sonarr API: {e}')
"
    fi
    
    if [ "$RADARR_URL" != "" ]; then
        echo "  ✅ Radarr configuré: $RADARR_URL"
        python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    config['radarr']['url'] = '$RADARR_URL'
    config['radarr']['enabled'] = True
    if 'symlink' in config:
        config['symlink']['radarr_url'] = '$RADARR_URL'
        config['symlink']['radarr_enabled'] = True
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
except Exception as e:
    print(f'Erreur configuration Radarr: {e}')
"
    fi
    
    if [ "$RADARR_API_KEY" != "" ]; then
        echo "  ✅ Clé API Radarr configurée"
        python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    config['radarr']['api_key'] = '$RADARR_API_KEY'
    if 'symlink' in config:
        config['symlink']['radarr_api_key'] = '$RADARR_API_KEY'
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
except Exception as e:
    print(f'Erreur configuration Radarr API: {e}')
"
    fi
fi

# Vérifier et initialiser la base de données
echo "💾 Vérification de la base de données..."
DB_DIR="/app/data"
DB_FILE="/app/data/redriva.db"

# S'assurer que le répertoire de base de données existe et a les bonnes permissions
if [ ! -d "$DB_DIR" ]; then
    echo "📁 Création du répertoire de base de données..."
    mkdir -p "$DB_DIR"
fi

# Tester l'écriture dans le répertoire de données
if [ ! -w "$DB_DIR" ]; then
    echo "❌ Erreur: Pas de permission d'écriture dans $DB_DIR"
    echo "💡 Vérifiez les permissions des volumes montés"
    ls -la "$DB_DIR"
else
    echo "✅ Permissions OK pour le répertoire de données"
fi

# Tester la création/écriture de la base de données
if [ -w "$DB_DIR" ]; then
    echo "🔧 Test de création de base de données..."
    if touch "$DB_FILE" 2>/dev/null; then
        echo "✅ Base de données accessible en écriture"
    else
        echo "❌ Impossible de créer le fichier de base de données"
    fi
fi

# Vérifier la configuration
if [ -f "$CONFIG_FILE" ]; then
    echo "✅ Configuration chargée"
else
    echo "⚠️ Aucune configuration trouvée, utilisation des valeurs par défaut"
fi

# Démarrer l'application
echo "🌐 Démarrage du serveur web..."
exec "$@"
