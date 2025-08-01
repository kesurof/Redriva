#!/bin/bash

echo "🔍 Vérification de la configuration Docker de Redriva"
echo "====================================================="

# Variables de couleur
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de logging
log_ok() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Compteur d'erreurs
errors=0

echo "🔧 Vérification des prérequis..."

# Vérifier Docker
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        log_ok "Docker est installé et fonctionne"
    else
        log_error "Docker est installé mais ne fonctionne pas"
        errors=$((errors + 1))
    fi
else
    log_error "Docker n'est pas installé"
    errors=$((errors + 1))
fi

# Vérifier Docker Compose
if command -v docker-compose &> /dev/null; then
    log_ok "Docker Compose est installé"
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    log_ok "Docker Compose (plugin) est installé"
    DOCKER_COMPOSE_CMD="docker compose"
else
    log_error "Docker Compose n'est pas installé"
    errors=$((errors + 1))
fi

echo ""
echo "📁 Vérification des fichiers..."

# Fichiers requis
required_files=(
    "Dockerfile"
    "docker-compose.yml"
    "requirements.txt"
    "src/main.py"
    "src/web.py"
    ".dockerignore"
    "docker-helper.sh"
    "build_docker.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        log_ok "Fichier $file présent"
    else
        log_error "Fichier $file manquant"
        errors=$((errors + 1))
    fi
done

# Vérifier les permissions des scripts
scripts=("docker-helper.sh" "build_docker.sh" "setup.sh")
for script in "${scripts[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            log_ok "Script $script exécutable"
        else
            log_warn "Script $script n'est pas exécutable (chmod +x $script)"
        fi
    fi
done

echo ""
echo "⚙️  Vérification de la configuration..."

# Vérifier les dossiers
if [ -d "config" ]; then
    log_ok "Dossier config/ présent"
    
    if [ -f "config/.env.example" ]; then
        log_ok "Fichier config/.env.example présent"
    else
        log_warn "Fichier config/.env.example manquant"
    fi
    
    if [ -f "config/.env" ]; then
        log_ok "Fichier config/.env présent"
        
        # Vérifier si le token est configuré
        if grep -q "votre_token_ici" config/.env; then
            log_warn "Token Real-Debrid non configuré dans config/.env"
        else
            log_ok "Token Real-Debrid semble configuré"
        fi
    else
        log_warn "Fichier config/.env manquant (exécutez ./setup.sh ou ./docker-helper.sh setup)"
    fi
else
    log_error "Dossier config/ manquant"
    errors=$((errors + 1))
fi

if [ -d "data" ]; then
    log_ok "Dossier data/ présent"
else
    log_warn "Dossier data/ manquant (sera créé automatiquement)"
fi

echo ""
echo "🐳 Test de la configuration Docker..."

# Vérifier la syntaxe du docker-compose.yml
if [ -n "$DOCKER_COMPOSE_CMD" ]; then
    if $DOCKER_COMPOSE_CMD config &> /dev/null; then
        log_ok "Fichier docker-compose.yml valide"
    else
        log_error "Erreur dans docker-compose.yml"
        errors=$((errors + 1))
    fi
else
    log_warn "Impossible de vérifier docker-compose.yml (Docker Compose non disponible)"
fi

# Test de construction de l'image (optionnel)
echo ""
echo "🔍 Test optionnel de construction d'image..."
echo "Voulez-vous tester la construction de l'image Docker ? (y/N)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "🔨 Test de construction en cours..."
    if docker build -t redriva:test . &> /dev/null; then
        log_ok "Construction de l'image réussie"
        # Nettoyer l'image de test
        docker rmi redriva:test &> /dev/null
    else
        log_error "Échec de la construction de l'image"
        errors=$((errors + 1))
    fi
fi

echo ""
echo "📊 Résumé de la vérification"
echo "============================"

if [ $errors -eq 0 ]; then
    log_ok "Toutes les vérifications sont passées !"
    echo ""
    echo "🚀 Prêt pour le déploiement Docker :"
    echo "   ./docker-helper.sh setup   # Configuration initiale"
    echo "   ./docker-helper.sh start   # Démarrage"
    echo ""
    echo "Ou manuellement :"
    echo "   docker-compose up -d       # Démarrage"
    echo "   docker-compose logs -f     # Voir les logs"
else
    log_error "$errors erreur(s) détectée(s)"
    echo ""
    echo "🔧 Actions recommandées :"
    echo "   1. Corrigez les erreurs listées ci-dessus"
    echo "   2. Relancez ce script pour vérifier"
    echo "   3. Consultez DOCKER.md pour plus d'aide"
    exit 1
fi
