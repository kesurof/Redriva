#!/bin/bash

echo "🐍 Redriva - Développement Local"
echo "================================"

# Vérification de la configuration
if [ ! -f "config/.env" ]; then
    echo "🔧 Configuration initiale..."
    ./setup.sh
    echo "⚠️  N'oubliez pas de configurer votre token Real-Debrid dans config/.env"
    echo ""
fi

# Variables d'environnement pour le développement
export FLASK_ENV=development
export FLASK_DEBUG=1
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "🚀 Démarrage en mode développement..."
echo "🌐 Accès: http://localhost:5000"
echo "🛑 Arrêt: Ctrl+C"
echo ""

# Démarrage direct avec Python en mode debug
cd src && python3 -u web.py
