#!/bin/bash

# Script de build local pour Redriva
# Compatible avec le workflow GitHub Actions

set -e

echo "🔨 Building Redriva..."

# Variables
REGISTRY="ghcr.io"
REPO="kesurof/redriva"
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
VERSION=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BUILDTIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Tag selon la branche
case $BRANCH in
  "main")
    TAG="latest"
    ;;
  "alpha")
    TAG="alpha"
    ;;
  "ssdv2")
    TAG="ssdv2"
    ;;
  *)
    TAG="$BRANCH"
    ;;
esac

echo "📦 Registry: $REGISTRY"
echo "🏷️  Repository: $REPO"
echo " Branch: $BRANCH"
echo "🏷️  Tag: $TAG"

# Build de l'image
docker build \
    --tag "$REGISTRY/$REPO:$TAG" \
    --build-arg BUILDTIME="$BUILDTIME" \
    --build-arg VERSION="$VERSION" \
    .

echo "✅ Image buildée avec succès!"
echo "🐳 Tag créé: $REGISTRY/$REPO:$TAG"

echo ""
echo "🚀 Pour tester localement:"
echo "   docker run -p 5000:5000 -e RD_TOKEN=your_token $REGISTRY/$REPO:$TAG"
echo ""
echo "🔧 Configuration complète:"
echo "   docker run -p 5000:5000 \\"
echo "     -e RD_TOKEN=\"your_token\" \\"
echo "     -e SONARR_URL=\"http://localhost:8989\" \\"
echo "     -e SONARR_API_KEY=\"your_sonarr_key\" \\"
echo "     -e RADARR_URL=\"http://localhost:7878\" \\"
echo "     -e RADARR_API_KEY=\"your_radarr_key\" \\"
echo "     $REGISTRY/$REPO:$TAG"
echo ""
echo "📋 Variables d'environnement supportées:"
echo "   - RD_TOKEN (obligatoire)"
echo "   - SONARR_URL, SONARR_API_KEY (optionnel)"
echo "   - RADARR_URL, RADARR_API_KEY (optionnel)"

echo ""
echo "📤 Pour push vers GHCR:"
echo "   docker push $REGISTRY/$REPO:$TAG"
