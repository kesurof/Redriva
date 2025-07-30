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
