#!/bin/bash

echo "🔍 Debug Docker Hub Authentication"
echo "=================================="

# Test de connexion Docker Hub
echo "1. Test de connexion Docker Hub..."

if [ -z "$DOCKERHUB_USERNAME" ] || [ -z "$DOCKERHUB_TOKEN" ]; then
    echo "❌ Variables d'environnement DOCKERHUB_USERNAME ou DOCKERHUB_TOKEN manquantes"
    echo "💡 Pour tester localement:"
    echo "   export DOCKERHUB_USERNAME=votre_username"
    echo "   export DOCKERHUB_TOKEN=votre_token"
    echo "   ./debug-docker-auth.sh"
    exit 1
fi

echo "✅ Variables d'environnement présentes"
echo "   Username: $DOCKERHUB_USERNAME"
echo "   Token: ${DOCKERHUB_TOKEN:0:10}..."

# Test de login
echo ""
echo "2. Test d'authentification..."
echo "$DOCKERHUB_TOKEN" | docker login --username "$DOCKERHUB_USERNAME" --password-stdin

if [ $? -eq 0 ]; then
    echo "✅ Authentification Docker Hub réussie"
    
    # Test de push d'une image test
    echo ""
    echo "3. Test de push (image test)..."
    
    # Créer une image test minimaliste
    cat > Dockerfile.test << EOF
FROM alpine:latest
RUN echo "Test image for Docker Hub auth" > /test.txt
CMD ["cat", "/test.txt"]
EOF
    
    docker build -f Dockerfile.test -t $DOCKERHUB_USERNAME/redriva:test-auth .
    
    if docker push $DOCKERHUB_USERNAME/redriva:test-auth; then
        echo "✅ Push test réussi"
        
        # Nettoyer l'image test
        docker rmi $DOCKERHUB_USERNAME/redriva:test-auth
        docker image prune -f
        rm Dockerfile.test
        
        echo ""
        echo "🎉 Authentification Docker Hub fonctionnelle !"
        echo "💡 Vous pouvez maintenant pousser vos images Redriva"
        
    else
        echo "❌ Échec du push test"
        echo "💡 Vérifiez les permissions de votre token Docker Hub"
    fi
    
else
    echo "❌ Échec de l'authentification Docker Hub"
    echo ""
    echo "🔧 Solutions possibles:"
    echo "   1. Vérifiez votre nom d'utilisateur Docker Hub"
    echo "   2. Régénérez votre token d'accès sur Docker Hub"
    echo "   3. Assurez-vous que le token a les permissions Read/Write"
    echo "   4. Vérifiez que le compte Docker Hub est actif"
fi

# Logout
docker logout
