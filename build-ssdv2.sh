#!/bin/bash

# Script de build pour image SSDV2
# Tag basé sur la branche GitHub: kesurof/redriva:ssdv2

set -e

echo "🔨 Building Redriva pour SSDV2..."

# Variables
REPO="kesurof/redriva"
TAG="ssdv2"
BRANCH=$(git branch --show-current 2>/dev/null || echo "alpha")

echo "📦 Repository: $REPO"
echo "🏷️  Tag: $TAG"
echo "🌿 Branch: $BRANCH"

# Build de l'image
docker build \
    --tag "$REPO:$TAG" \
    --tag "$REPO:$TAG-$BRANCH" \
    --label "org.opencontainers.image.revision=$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
    --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    .

echo "✅ Image buildée avec succès!"
echo "🐳 Tags créés:"
echo "   - $REPO:$TAG"
echo "   - $REPO:$TAG-$BRANCH"

echo ""
echo "🚀 Pour tester localement:"
echo "   docker run -p 5000:5000 -e RD_TOKEN=your_token $REPO:$TAG"

echo ""
echo "📤 Pour push vers le registry:"
echo "   docker push $REPO:$TAG"
echo "   docker push $REPO:$TAG-$BRANCH"
