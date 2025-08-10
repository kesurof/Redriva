#!/bin/bash

# Script de build et test complet pour Redriva
set -e

echo "🔨 Construction et test de Redriva Docker"
echo "========================================="

# Variables
IMAGE_NAME="kesurof/redriva"
CONTAINER_NAME="redriva-test"
TEST_PORT="8001"

# Nettoyage préalable
echo "🧹 Nettoyage des containers et images existants..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Construction de l'image
echo "🏗️  Construction de l'image Docker..."
docker build -t $IMAGE_NAME .

if [ $? -eq 0 ]; then
    echo "✅ Image construite avec succès !"
else
    echo "❌ Erreur lors de la construction de l'image"
    exit 1
fi

# Test de l'image
echo "🚀 Test de démarrage du container..."

# Création des répertoires de test
TEST_DIR="/tmp/redriva-test"
mkdir -p $TEST_DIR/config
mkdir -p $TEST_DIR/data
chmod 777 $TEST_DIR/config
chmod 777 $TEST_DIR/data

# Démarrage du container de test
docker run -d \
    --name $CONTAINER_NAME \
    -p $TEST_PORT:5000 \
    -v $TEST_DIR/config:/app/config \
    -v $TEST_DIR/data:/app/data \
    -e PUID=1000 \
    -e PGID=1000 \
    $IMAGE_NAME

echo "⏳ Attente du démarrage du service..."
sleep 10

# Vérification que le container tourne
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "❌ Le container ne démarre pas correctement"
    echo "📋 Logs du container :"
    docker logs $CONTAINER_NAME
    exit 1
fi

# Test de l'interface web
echo "🌐 Test de l'interface web..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$TEST_PORT | grep -q "200"; then
    echo "✅ Interface web accessible sur http://localhost:$TEST_PORT"
else
    echo "⚠️  Interface web pas encore accessible, vérifiez les logs"
fi

# Affichage des logs récents
echo "📋 Logs récents du container :"
docker logs --tail 20 $CONTAINER_NAME

echo ""
echo "🎉 Test terminé !"
echo "=================="
echo "🌐 Interface de test : http://localhost:$TEST_PORT"
echo "📁 Répertoire config test : $TEST_DIR/config"
echo "📁 Répertoire data test : $TEST_DIR/data"
echo ""
echo "📋 Commandes utiles :"
echo "  • docker logs $CONTAINER_NAME              (voir tous les logs)"
echo "  • docker exec -it $CONTAINER_NAME bash     (accès au container)"
echo "  • docker stop $CONTAINER_NAME              (arrêter le test)"
echo "  • docker rm $CONTAINER_NAME                (supprimer le container)"
echo ""
echo "🔧 Pour nettoyer après test :"
echo "  ./cleanup-test.sh"
