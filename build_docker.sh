#!/bin/bash

echo "🐳 Construction de l'image Docker Redriva"
echo "========================================="

# Variables
IMAGE_NAME="kesurof/redriva"
TAG="latest"
FULL_TAG="${IMAGE_NAME}:${TAG}"

# Vérification que Docker est disponible
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé ou n'est pas dans le PATH"
    exit 1
fi

# Vérifier que Docker fonctionne
if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas en cours d'exécution"
    echo "💡 Démarrez le service Docker"
    exit 1
fi

# Vérifier les fichiers nécessaires
echo "🔍 Vérification des fichiers nécessaires..."
REQUIRED_FILES=("Dockerfile" "requirements.txt" "src/main.py" "src/web.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Fichier manquant: $file"
        exit 1
    fi
done
echo "✅ Tous les fichiers nécessaires sont présents"

# Construction de l'image
echo "🔨 Construction de l'image ${FULL_TAG}..."
docker build -t "${FULL_TAG}" .

# Vérification du résultat
if [ $? -eq 0 ]; then
    echo "✅ Image construite avec succès: ${FULL_TAG}"
    
    # Affichage des informations sur l'image
    echo ""
    echo "📋 Informations sur l'image:"
    docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    
    # Test rapide de l'image
    echo ""
    echo "🧪 Test rapide de l'image..."
    if docker run --rm "${FULL_TAG}" python -c "import src.main; print('✅ Import principal OK')"; then
        echo "✅ Test d'import réussi"
    else
        echo "⚠️  Avertissement: Test d'import échoué"
    fi
    
    echo ""
    echo "🚀 Commandes utiles:"
    echo "   Tester localement: docker run -p 5000:5000 -v \$(pwd)/data:/app/data -v \$(pwd)/config:/app/config ${FULL_TAG}"
    echo "   Pousser vers Docker Hub: docker push ${FULL_TAG}"
    echo "   Lancer avec docker-compose: docker-compose up -d"
    echo "   Utiliser l'assistant: ./docker-helper.sh start"
    
else
    echo "❌ Erreur lors de la construction de l'image"
    exit 1
fi
