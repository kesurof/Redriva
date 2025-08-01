#!/bin/bash

echo "🚀 Configuration initiale de Redriva"
echo "===================================="

# Création des dossiers
echo "📁 Création des dossiers nécessaires..."
mkdir -p config data

# Configuration du token
if [ ! -f "config/.env" ]; then
    echo ""
    echo "⚙️ Configuration du token Real-Debrid"
    echo "Création du fichier de configuration config/.env..."
    
    if [ -f "config/.env.example" ]; then
        cp config/.env.example config/.env
        echo "✅ Fichier config/.env créé depuis config/.env.example"
    else
        echo "# Configuration Redriva - Real-Debrid Token" > config/.env
        echo "# Token Real-Debrid (obligatoire)" >> config/.env
        echo "RD_TOKEN=votre_token_ici" >> config/.env
        echo "" >> config/.env
        echo "# Paramètres optionnels Real-Debrid" >> config/.env
        echo "RD_MAX_CONCURRENT=50" >> config/.env
        echo "RD_BATCH_SIZE=250" >> config/.env
        echo "RD_QUOTA_WAIT=60" >> config/.env
        echo "RD_TORRENT_WAIT=10" >> config/.env
        echo "" >> config/.env
        echo "# Configuration Flask (pour environnements Docker)" >> config/.env
        echo "FLASK_HOST=0.0.0.0" >> config/.env
        echo "FLASK_PORT=5000" >> config/.env
        echo "FLASK_DEBUG=false" >> config/.env
        echo "" >> config/.env
        echo "# Configuration Gunicorn (pour optimiser les performances en production)" >> config/.env
        echo "GUNICORN_WORKERS=2" >> config/.env
        echo "GUNICORN_TIMEOUT=120" >> config/.env
        echo "GUNICORN_KEEPALIVE=5" >> config/.env
        echo "✅ Fichier config/.env créé avec modèle de base"
    fi
    
    echo ""
    echo "🔧 Étapes suivantes :"
    echo "1. Éditez le fichier config/.env avec votre token Real-Debrid :"
    echo "   nano config/.env"
    echo "2. Remplacez 'votre_token_ici' par votre vrai token"
else
    echo "✅ Configuration existante détectée dans config/.env"
fi

echo ""
echo "📋 Comment obtenir votre token Real-Debrid :"
echo "1. Connectez-vous sur https://real-debrid.com"
echo "2. Allez dans 'Mon compte' → 'API'"  
echo "3. Copiez votre token d'accès"
echo "4. Collez-le dans config/.env à la place de 'votre_token_ici'"

echo ""
echo "🎯 Tests rapides pour vérifier l'installation :"
echo "   python src/main.py --stats"
echo "   python src/main.py --torrents-only"

echo ""
echo "✅ Configuration terminée ! Vous pouvez maintenant utiliser Redriva."
