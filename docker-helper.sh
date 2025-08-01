#!/bin/bash

echo "🐳 Assistant Docker pour Redriva"
echo "================================="

# Fonction d'aide
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commandes disponibles:"
    echo "  setup     - Configuration initiale (crée .env, vérifie Docker)"
    echo "  build     - Construit l'image Docker locale"
    echo "  start     - Démarre les conteneurs (docker-compose up -d)"
    echo "  stop      - Arrête les conteneurs"
    echo "  restart   - Redémarre les conteneurs"
    echo "  logs      - Affiche les logs en temps réel"
    echo "  status    - Affiche l'état des conteneurs"
    echo "  clean     - Nettoie les images/conteneurs inutilisés"
    echo "  update    - Met à jour vers la dernière version"
    echo "  shell     - Accès shell dans le conteneur"
    echo "  help      - Affiche cette aide"
}

# Vérifications préalables
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker n'est pas installé"
        echo "💡 Installation requise: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Détecter quelle commande Docker Compose utiliser
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        echo "❌ Docker Compose n'est pas installé"
        echo "💡 Installation requise: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo "❌ Docker n'est pas en cours d'exécution"
        echo "💡 Démarrez le service Docker"
        exit 1
    fi
}

# Configuration initiale
setup_redriva() {
    echo "🔧 Configuration initiale de Redriva..."
    
    # Exécuter le script setup existant
    if [ -f "./setup.sh" ]; then
        chmod +x ./setup.sh
        ./setup.sh
    else
        echo "❌ Script setup.sh introuvable"
        exit 1
    fi
    
    # Vérifier la configuration
    if [ ! -f "config/.env" ]; then
        echo "❌ Fichier config/.env non trouvé"
        echo "💡 Exécutez d'abord: ./setup.sh"
        exit 1
    fi
    
    # Vérifier le token
    if grep -q "votre_token_ici" config/.env; then
        echo "⚠️  Token Real-Debrid non configuré"
        echo "💡 Éditez config/.env et remplacez 'votre_token_ici' par votre vrai token"
        echo "📖 Obtenir un token: https://real-debrid.com/apitoken"
    else
        echo "✅ Configuration semble correcte"
    fi
    
    echo "🎯 Prêt pour: ./docker-helper.sh start"
}

# Construction de l'image
build_image() {
    echo "🔨 Construction de l'image Docker..."
    check_docker
    
    if [ -f "./build_docker.sh" ]; then
        chmod +x ./build_docker.sh
        ./build_docker.sh
    else
        echo "🔨 Construction manuelle..."
        docker build -t kesurof/redriva:latest .
    fi
}

# Démarrage des services
start_services() {
    echo "🚀 Démarrage de Redriva..."
    check_docker
    
    if [ ! -f "config/.env" ]; then
        echo "❌ Configuration manquante"
        echo "💡 Exécutez d'abord: $0 setup"
        exit 1
    fi
    
    $DOCKER_COMPOSE_CMD up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Redriva démarré avec succès"
        echo "🌐 Accès: http://localhost:5000"
        echo "📊 Logs: $0 logs"
        echo "🔍 Statut: $0 status"
    else
        echo "❌ Erreur lors du démarrage"
        echo "💡 Vérifiez: $0 logs"
    fi
}

# Arrêt des services
stop_services() {
    echo "🛑 Arrêt de Redriva..."
    $DOCKER_COMPOSE_CMD down
    echo "✅ Redriva arrêté"
}

# Redémarrage des services
restart_services() {
    echo "🔄 Redémarrage de Redriva..."
    stop_services
    sleep 2
    start_services
}

# Affichage des logs
show_logs() {
    echo "📋 Logs de Redriva (Ctrl+C pour quitter)..."
    $DOCKER_COMPOSE_CMD logs -f
}

# Statut des conteneurs
show_status() {
    echo "📊 Statut des conteneurs Redriva:"
    $DOCKER_COMPOSE_CMD ps
    echo ""
    echo "🔍 Santé des conteneurs:"
    docker ps --filter "name=redriva" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Nettoyage
clean_docker() {
    echo "🧹 Nettoyage Docker..."
    echo "Suppression des images inutilisées..."
    docker image prune -f
    echo "Suppression des volumes inutilisés..."
    docker volume prune -f
    echo "✅ Nettoyage terminé"
}

# Mise à jour
update_redriva() {
    echo "📥 Mise à jour de Redriva..."
    
    # Arrêter les services
    $DOCKER_COMPOSE_CMD down
    
    # Récupérer la dernière image
    docker pull kesurof/redriva:latest
    
    # Redémarrer
    start_services
}

# Accès shell
access_shell() {
    echo "🐚 Accès shell au conteneur Redriva..."
    $DOCKER_COMPOSE_CMD exec redriva /bin/bash
}

# Parse command line arguments
case "${1:-help}" in
    setup)
        setup_redriva
        ;;
    build)
        build_image
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    clean)
        clean_docker
        ;;
    update)
        update_redriva
        ;;
    shell)
        access_shell
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Commande inconnue: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
