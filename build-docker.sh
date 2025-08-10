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
echo "📤 Pour push vers GHCR:"
echo "   docker push $REGISTRY/$REPO:$TAG"
