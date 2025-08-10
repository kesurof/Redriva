#!/bin/bash
# Script simple pour SSDV2

echo "🚀 Redriva SSDV2 Setup"

# Variables
REDRIVA_DIR="/opt/seedbox/docker/${USER}/redriva"

# Vérification SSDV2
if [ ! -d "/opt/seedbox" ]; then
    echo "❌ SSDV2 non détecté"
    exit 1
fi

# Création des répertoires
mkdir -p "$REDRIVA_DIR"/{config,data}

# Copie de la configuration
cp config/config.json "$REDRIVA_DIR/config/"
cp ssdv2-compose.yml "$REDRIVA_DIR/docker-compose.yml"

echo "✅ Configuration créée dans: $REDRIVA_DIR"
echo " Image Docker: ghcr.io/kesurof/redriva:ssdv2"
echo ""
echo "📋 Prochaines étapes:"
echo "1. cd $REDRIVA_DIR"
echo "2. Lancez le conteneur puis configurez via l'interface web (http://localhost:5000)"
