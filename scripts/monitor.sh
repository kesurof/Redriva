#!/bin/bash
# 🔍 Script de Monitoring Redriva en Temps Réel
# Usage: ./monitor.sh [container_name]

CONTAINER=${1:-redriva}

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Vérifier que le conteneur existe
if ! docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}❌ Conteneur '$CONTAINER' non trouvé${NC}"
    exit 1
fi

# Fonction pour afficher avec timestamp
log_with_time() {
    local color="$1"
    local icon="$2" 
    local message="$3"
    echo -e "${color}${icon} $(date '+%H:%M:%S') - ${message}${NC}"
}

echo -e "${BLUE}🔍 Monitoring Redriva en temps réel...${NC}"
echo -e "${BLUE}Container: $CONTAINER${NC}"
echo -e "${BLUE}Appuyez sur Ctrl+C pour arrêter${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Trap pour gérer Ctrl+C proprement
trap 'echo -e "\n${BLUE}👋 Arrêt du monitoring...${NC}"; exit 0' INT

# Monitoring en temps réel
docker logs -f "$CONTAINER" 2>/dev/null | while IFS= read -r line; do
    # Synchronisations
    if echo "$line" | grep -q '^\[SYNC_START'; then
        MODE=$(echo "$line" | grep -o 'mode=[a-z_]*' | cut -d= -f2)
        log_with_time "$BLUE" "🚀" "SYNC DÉMARRÉE ($MODE)"
        
    elif echo "$line" | grep -q '^\[SYNC_END.*status=success'; then
        MODE=$(echo "$line" | grep -o 'mode=[a-z_]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        TORRENTS=$(echo "$line" | grep -o 'torrents=[0-9]*' | cut -d= -f2)
        RATE=$(echo "$line" | grep -o 'rate=[0-9.]*' | cut -d= -f2)
        
        DETAILS="Mode: $MODE"
        [ -n "$DURATION" ] && DETAILS="$DETAILS | Durée: ${DURATION}s"
        [ -n "$TORRENTS" ] && DETAILS="$DETAILS | Torrents: $TORRENTS"
        [ -n "$RATE" ] && DETAILS="$DETAILS | Vitesse: ${RATE}/s"
        
        log_with_time "$GREEN" "✅" "SYNC RÉUSSIE ($DETAILS)"
        
    elif echo "$line" | grep -q '^\[SYNC_ABORT'; then
        log_with_time "$YELLOW" "⚠️" "SYNC ANNULÉE"
        
    # Phases de sync smart
    elif echo "$line" | grep -q '^\[SYNC_PHASE_START'; then
        PHASE=$(echo "$line" | grep -o 'phase=[0-9]*' | cut -d= -f2)
        DESC=$(echo "$line" | grep -o 'description="[^"]*"' | cut -d'"' -f2)
        log_with_time "$CYAN" "📋" "Phase $PHASE: $DESC"
        
    elif echo "$line" | grep -q '^\[SYNC_PHASE_END'; then
        PHASE=$(echo "$line" | grep -o 'phase=[0-9]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        log_with_time "$CYAN" "📋" "Phase $PHASE terminée (${DURATION}s)"
        
    # Health checks
    elif echo "$line" | grep -q '^\[HEALTH_CHECK_START'; then
        log_with_time "$PURPLE" "🏥" "HEALTH CHECK DÉMARRÉ"
        
    elif echo "$line" | grep -q '^\[HEALTH_CHECK_END'; then
        CHECKED=$(echo "$line" | grep -o 'checked=[0-9]*' | cut -d= -f2)
        ERRORS=$(echo "$line" | grep -o 'errors=[0-9]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        
        DETAILS=""
        [ -n "$CHECKED" ] && DETAILS="Vérifiés: $CHECKED"
        [ -n "$ERRORS" ] && DETAILS="$DETAILS | Erreurs 503: $ERRORS"
        [ -n "$DURATION" ] && DETAILS="$DETAILS | Durée: ${DURATION}s"
        
        if [ "${ERRORS:-0}" -gt 0 ]; then
            log_with_time "$YELLOW" "🏥" "HEALTH CHECK ($DETAILS)"
        else
            log_with_time "$PURPLE" "🏥" "HEALTH CHECK ($DETAILS)"
        fi
        
    # Nettoyages
    elif echo "$line" | grep -q '^\[CLEAN_START'; then
        log_with_time "$BLUE" "🧹" "NETTOYAGE DÉMARRÉ"
        
    elif echo "$line" | grep -q '^\[CLEAN_END'; then
        DELETED=$(echo "$line" | grep -o 'deleted=[0-9]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        
        DETAILS=""
        [ -n "$DELETED" ] && DETAILS="Supprimés: $DELETED"
        [ -n "$DURATION" ] && DETAILS="$DETAILS | Durée: ${DURATION}s"
        
        log_with_time "$BLUE" "🧹" "NETTOYAGE TERMINÉ ($DETAILS)"
        
    # Suppressions de torrents
    elif echo "$line" | grep -q '^\[TORRENT_DELETE_END.*status=success'; then
        TORRENT_ID=$(echo "$line" | grep -o 'torrent_id=[a-zA-Z0-9]*' | cut -d= -f2)
        log_with_time "$YELLOW" "🗑️" "TORRENT SUPPRIMÉ (ID: $TORRENT_ID)"
        
    # Batch suppressions  
    elif echo "$line" | grep -q '^\[BATCH_DELETE_START'; then
        COUNT=$(echo "$line" | grep -o 'count=[0-9]*' | cut -d= -f2)
        log_with_time "$YELLOW" "🗑️" "SUPPRESSION EN LOT DÉMARRÉE ($COUNT torrents)"
        
    elif echo "$line" | grep -q '^\[BATCH_DELETE_PROGRESS'; then
        PROGRESS=$(echo "$line" | grep -o 'progress=[0-9]*' | cut -d= -f2)
        TOTAL=$(echo "$line" | grep -o 'total=[0-9]*' | cut -d= -f2)
        PERCENTAGE=$(echo "scale=1; $PROGRESS * 100 / $TOTAL" | bc 2>/dev/null || echo "?")
        log_with_time "$YELLOW" "⏳" "SUPPRESSION EN LOT: $PROGRESS/$TOTAL (${PERCENTAGE}%)"
        
    elif echo "$line" | grep -q '^\[BATCH_DELETE_END'; then
        DELETED=$(echo "$line" | grep -o 'deleted=[0-9]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        log_with_time "$YELLOW" "🗑️" "SUPPRESSION EN LOT TERMINÉE ($DELETED supprimés en ${DURATION}s)"
        
    # Base de données
    elif echo "$line" | grep -q '^\[DB_CHECK_START'; then
        log_with_time "$CYAN" "💾" "VÉRIFICATION DB DÉMARRÉE"
        
    elif echo "$line" | grep -q '^\[DB_CHECK_END'; then
        log_with_time "$CYAN" "💾" "VÉRIFICATION DB TERMINÉE"
        
    # Tâches async
    elif echo "$line" | grep -q '^\[ASYNC_TASK_START'; then
        TASK=$(echo "$line" | grep -o 'task="[^"]*"' | cut -d'"' -f2)
        log_with_time "$BLUE" "⚡" "TÂCHE ASYNC DÉMARRÉE ($TASK)"
        
    elif echo "$line" | grep -q '^\[ASYNC_TASK_END'; then
        TASK=$(echo "$line" | grep -o 'task="[^"]*"' | cut -d'"' -f2)
        STATUS=$(echo "$line" | grep -o 'status=[a-z]*' | cut -d= -f2)
        DURATION=$(echo "$line" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        
        if [ "$STATUS" = "success" ]; then
            log_with_time "$GREEN" "⚡" "TÂCHE ASYNC TERMINÉE ($TASK - ${DURATION}s)"
        else
            log_with_time "$RED" "⚡" "TÂCHE ASYNC ÉCHOUÉE ($TASK - ${DURATION}s)"
        fi
        
    # Erreurs générales
    elif echo "$line" | grep -q '^\[.*status=error'; then
        TYPE=$(echo "$line" | sed 's/^\[\([^_]*\)_.*/\1/')
        ERROR_MSG=$(echo "$line" | grep -o 'error="[^"]*"' | cut -d'"' -f2)
        
        DETAILS="Type: $TYPE"
        [ -n "$ERROR_MSG" ] && DETAILS="$DETAILS | Erreur: $ERROR_MSG"
        
        log_with_time "$RED" "❌" "ERREUR ($DETAILS)"
        
    # Triggers depuis l'interface web
    elif echo "$line" | grep -q '^\[SYNC_TRIGGER'; then
        SOURCE=$(echo "$line" | grep -o 'source="[^"]*"' | cut -d'"' -f2)
        log_with_time "$BLUE" "🌐" "SYNC DÉCLENCHÉE (Web: $SOURCE)"
        
    elif echo "$line" | grep -q '^\[CLEAN_TRIGGER'; then
        log_with_time "$BLUE" "🌐" "NETTOYAGE DÉCLENCHÉ (Web)"
        
    # Autres événements importants
    elif echo "$line" | grep -q '^\[UNAVAILABLE_CLEAN'; then
        log_with_time "$BLUE" "🧹" "NETTOYAGE FICHIERS INDISPONIBLES"
        
    elif echo "$line" | grep -q '^\[STATS_REFRESH'; then
        log_with_time "$CYAN" "📊" "RAFRAÎCHISSEMENT STATISTIQUES"
    fi
done
