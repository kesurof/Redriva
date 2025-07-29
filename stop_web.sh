#!/bin/bash
echo "🛑 Arrêt forcé de l'interface web Redriva..."

# 1. Tuer les processus web.py
echo "📋 Recherche des processus web.py..."
pkill -f "python.*web.py" && echo "✅ Processus web.py arrêtés" || echo "ℹ️ Aucun processus web.py trouvé"

# 2. Libérer le port 5000
echo "🔓 Libération du port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null && echo "✅ Port 5000 libéré" || echo "ℹ️ Port 5000 déjà libre"

# 3. Nettoyer tous les processus Redriva suspendus
echo "🧹 Nettoyage des processus Redriva..."
pkill -f "Redriva" 2>/dev/null && echo "✅ Processus Redriva nettoyés" || echo "ℹ️ Aucun processus Redriva restant"

# 4. Vérification finale
echo "🔍 Vérification finale..."
if lsof -i:5000 >/dev/null 2>&1; then
    echo "⚠️ Le port 5000 est encore utilisé:"
    lsof -i:5000
else
    echo "✅ Port 5000 complètement libre"
fi

echo "🎉 Nettoyage terminé. Vous pouvez relancer le serveur."
