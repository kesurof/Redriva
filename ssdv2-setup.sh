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

# Création du .env
cat > "$REDRIVA_DIR/.env" << EOF
# Configuration SSDV2 Redriva
RD_TOKEN=your_real_debrid_token_here
PUID=1000
PGID=1000
TZ=Europe/Paris
DOMAIN=your_domain.com
EOF

echo "✅ Configuration créée dans: $REDRIVA_DIR"
echo "📝 Éditez le token dans: $REDRIVA_DIR/.env"
echo "🐳 Image Docker: kesurof/redriva:ssdv2"
echo ""
echo "📋 Prochaines étapes:"
echo "1. cd $REDRIVA_DIR"
echo "2. nano .env (configurer RD_TOKEN et DOMAIN)"
echo "3. docker-compose up -d"
