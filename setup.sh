#!/bin/bash

echo "🚀 Configuration initiale de Redriva"
echo "===================================="

# Création des dossiers
echo "📁 Création des dossiers nécessaires..."
mkdir -p config data

# Configuration du token
if [ ! -f "config/rd_token.conf" ] && [ ! -f ".env" ]; then
    echo ""
    echo "⚙️ Configuration du token Real-Debrid"
    echo "Choisissez une méthode de configuration :"
    echo "1) Fichier .env (recommandé)"
    echo "2) Fichier config/rd_token.conf"
    echo "3) Variable d'environnement uniquement"
    
    read -p "Votre choix (1-3): " choice
    
    case $choice in
        1)
            if [ ! -f ".env" ]; then
                cp .env.example .env
                echo "✅ Fichier .env créé depuis .env.example"
                echo "🔧 Éditez maintenant le fichier .env avec votre token Real-Debrid"
                echo "   nano .env"
            fi
            ;;
        2)
            if [ ! -f "config/rd_token.conf" ]; then
                cp config/rd_token.conf.example config/rd_token.conf
                echo "✅ Fichier rd_token.conf créé depuis l'exemple"
                echo "🔧 Éditez maintenant le fichier avec votre token Real-Debrid"
                echo "   nano config/rd_token.conf"
            fi
            ;;
        3)
            echo "💡 Utilisez cette commande pour définir votre token :"
            echo "   export RD_TOKEN=\"votre_token_real_debrid\""
            ;;
        *)
            echo "❌ Choix invalide"
            exit 1
            ;;
    esac
else
    echo "✅ Configuration existante détectée"
fi

echo ""
echo "📋 Comment obtenir votre token Real-Debrid :"
echo "1. Connectez-vous sur https://real-debrid.com"
echo "2. Allez dans 'Mon compte' → 'API'"
echo "3. Copiez votre token d'accès"

echo ""
echo "🎯 Tests rapides pour vérifier l'installation :"
echo "   python src/main.py --stats"
echo "   python src/main.py --torrents-only"

echo ""
echo "✅ Configuration terminée ! Vous pouvez maintenant utiliser Redriva."
