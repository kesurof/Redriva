#!/bin/bash
# Script d'installation Redriva pour SSDV2
# Usage: ./install-ssdv2.sh

set -e

echo "🚀 Installation Redriva pour SSDV2"
echo "=================================="

# Variables
REDRIVA_DIR="/opt/seedbox/docker/${USER}/redriva"
CONFIG_DIR="${REDRIVA_DIR}/config"
DATA_DIR="${REDRIVA_DIR}/data"

# Vérification SSDV2
if [ ! -d "/opt/seedbox" ]; then
    echo "❌ SSDV2 non détecté. Ce script est conçu pour SSDV2."
    exit 1
fi

echo "✅ Environnement SSDV2 détecté"

# Création des répertoires
echo "📁 Création des répertoires..."
sudo mkdir -p "$CONFIG_DIR" "$DATA_DIR"
sudo chown -R $USER:$USER "$REDRIVA_DIR"

# Copie de la configuration
echo "📋 Installation de la configuration..."
cp config/conf.ssdv2.json "$CONFIG_DIR/conf.json"

# Configuration des permissions
chmod 644 "$CONFIG_DIR"/*
chmod 755 "$DATA_DIR"

echo "✅ Installation terminée !"
echo ""
echo "🔧 Prochaines étapes:"
echo "1. Configurez votre token via l'interface web Redriva (http://localhost:5000)"
echo "2. Déployez avec SSDV2: ansible-playbook site.yml -t redriva"
echo "3. Accédez à l'interface: https://redriva.votre-domaine.com"
echo ""
echo "📖 Documentation: https://github.com/kesurof/redriva"
