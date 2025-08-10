#!/bin/bash

# Script d'entrée pour Redriva Docker
# Gère la configuration via variables d'environnement

echo "🚀 Démarrage de Redriva..."

# Créer le fichier de configuration depuis les variables d'environnement si elles sont définies
CONFIG_FILE="/app/config/config.json"

if [ ! -f "$CONFIG_FILE" ] || [ "$RD_TOKEN" != "" ]; then
    echo "🔧 Configuration depuis les variables d'environnement..."
    
    # Copier le template par défaut
    cp /app/config/config.example.json "$CONFIG_FILE"
    
    # Remplacer les valeurs si les variables d'environnement sont définies
    if [ "$RD_TOKEN" != "" ]; then
        echo "  ✅ Token Real-Debrid configuré"
        sed -i "s/\"token\": \"\"/\"token\": \"$RD_TOKEN\"/g" "$CONFIG_FILE"
        sed -i "s/\"setup_completed\": false/\"setup_completed\": true/g" "$CONFIG_FILE"
    fi
    
    if [ "$SONARR_URL" != "" ]; then
        echo "  ✅ Sonarr configuré: $SONARR_URL"
        sed -i "s|\"url\": \"\"|\"url\": \"$SONARR_URL\"|g" "$CONFIG_FILE"
        sed -i "s/\"enabled\": false/\"enabled\": true/g" "$CONFIG_FILE"
    fi
    
    if [ "$SONARR_API_KEY" != "" ]; then
        echo "  ✅ Clé API Sonarr configurée"
        sed -i "s/\"api_key\": \"\"/\"api_key\": \"$SONARR_API_KEY\"/g" "$CONFIG_FILE"
    fi
    
    if [ "$RADARR_URL" != "" ]; then
        echo "  ✅ Radarr configuré: $RADARR_URL"
        # Pour Radarr, on doit cibler spécifiquement la section radarr
        python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['radarr']['url'] = '$RADARR_URL'
config['radarr']['enabled'] = True
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"
    fi
    
    if [ "$RADARR_API_KEY" != "" ]; then
        echo "  ✅ Clé API Radarr configurée"
        python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['radarr']['api_key'] = '$RADARR_API_KEY'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"
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
