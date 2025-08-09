#!/bin/bash
# 📊 Script de Résumé Quotidien Redriva
# Usage: ./daily_summary.sh [container_name]

CONTAINER=${1:-redriva}

echo "📊 Résumé Redriva - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Vérifier que le conteneur existe
if ! docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo "❌ Conteneur '$CONTAINER' non trouvé"
    exit 1
fi

# Fonction pour extraire des valeurs des logs
extract_value() {
    local pattern="$1"
    local field="$2"
    docker logs "$CONTAINER" --since 24h | grep "$pattern" | \
        grep -o "${field}=[0-9]*" | cut -d= -f2 | tail -1
}

# Synchronisations
echo "🔄 SYNCHRONISATIONS (24h)"
SYNC_COUNT=$(docker logs "$CONTAINER" --since 24h | grep '^\[SYNC_END' | wc -l)
SYNC_SUCCESS=$(docker logs "$CONTAINER" --since 24h | grep '^\[SYNC_END.*status=success' | wc -l)
SYNC_ERROR=$(docker logs "$CONTAINER" --since 24h | grep '^\[SYNC_END.*status=error' | wc -l)

echo "   Total: $SYNC_COUNT | Réussies: $SYNC_SUCCESS | Échecs: $SYNC_ERROR"

if [ "$SYNC_COUNT" -gt 0 ]; then
    SUCCESS_RATE=$(echo "scale=1; $SYNC_SUCCESS * 100 / $SYNC_COUNT" | bc 2>/dev/null || echo "N/A")
    echo "   Taux de réussite: ${SUCCESS_RATE}%"
fi

# Dernière synchronisation
LAST_SYNC=$(docker logs "$CONTAINER" | grep '^\[SYNC_END' | tail -1)
if [ -n "$LAST_SYNC" ]; then
    echo "   Dernière: $LAST_SYNC"
    
    # Extraire les stats de la dernière sync
    LAST_TORRENTS=$(echo "$LAST_SYNC" | grep -o 'torrents=[0-9]*' | cut -d= -f2)
    LAST_DETAILS=$(echo "$LAST_SYNC" | grep -o 'details=[0-9]*' | cut -d= -f2)
    LAST_DURATION=$(echo "$LAST_SYNC" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
    
    [ -n "$LAST_TORRENTS" ] && echo "   └─ Torrents: $LAST_TORRENTS"
    [ -n "$LAST_DETAILS" ] && echo "   └─ Détails: $LAST_DETAILS"  
    [ -n "$LAST_DURATION" ] && echo "   └─ Durée: ${LAST_DURATION}s"
fi

echo ""

# Vérifications de santé
echo "🏥 VÉRIFICATIONS DE SANTÉ (24h)"
HEALTH_COUNT=$(docker logs "$CONTAINER" --since 24h | grep '^\[HEALTH_CHECK_END' | wc -l)
echo "   Nombre de checks: $HEALTH_COUNT"

if [ "$HEALTH_COUNT" -gt 0 ]; then
    LAST_HEALTH=$(docker logs "$CONTAINER" | grep '^\[HEALTH_CHECK_END' | tail -1)
    if [ -n "$LAST_HEALTH" ]; then
        HEALTH_CHECKED=$(echo "$LAST_HEALTH" | grep -o 'checked=[0-9]*' | cut -d= -f2)
        HEALTH_ERRORS=$(echo "$LAST_HEALTH" | grep -o 'errors=[0-9]*' | cut -d= -f2)
        HEALTH_DURATION=$(echo "$LAST_HEALTH" | grep -o 'duration=[0-9.]*' | cut -d= -f2)
        
        echo "   Dernier check:"
        [ -n "$HEALTH_CHECKED" ] && echo "   └─ Vérifiés: $HEALTH_CHECKED"
        [ -n "$HEALTH_ERRORS" ] && echo "   └─ Erreurs 503: $HEALTH_ERRORS"
        [ -n "$HEALTH_DURATION" ] && echo "   └─ Durée: ${HEALTH_DURATION}s"
    fi
fi

echo ""

# Nettoyages
echo "🧹 NETTOYAGES (24h)"
CLEAN_COUNT=$(docker logs "$CONTAINER" --since 24h | grep '^\[CLEAN_END' | wc -l)
echo "   Nombre de nettoyages: $CLEAN_COUNT"

# Suppression de torrents
DELETE_COUNT=$(docker logs "$CONTAINER" --since 24h | grep '^\[TORRENT_DELETE_END.*status=success' | wc -l)
echo "   Torrents supprimés: $DELETE_COUNT"

# Batch suppressions
BATCH_COUNT=$(docker logs "$CONTAINER" --since 24h | grep '^\[BATCH_DELETE_END' | wc -l)
echo "   Suppressions en lot: $BATCH_COUNT"

echo ""

# Erreurs globales
echo "❌ ERREURS (24h)"
ERROR_COUNT=$(docker logs "$CONTAINER" --since 24h | egrep '^\[.*status=error' | wc -l)
echo "   Total erreurs: $ERROR_COUNT"

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "   Types d'erreurs:"
    docker logs "$CONTAINER" --since 24h | egrep '^\[.*status=error' | \
        sed 's/^\[\([^_]*\)_.*/   └─ \1/' | sort | uniq -c | \
        awk '{print "      " $2 ": " $1}'
fi

echo ""

# Performances
echo "📈 PERFORMANCES"

# Moyenne durée sync
AVG_SYNC_DURATION=$(docker logs "$CONTAINER" --since 24h | grep '^\[SYNC_END.*status=success' | \
    grep -o 'duration=[0-9.]*' | cut -d= -f2 | \
    awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count; else print "N/A"}')
echo "   Durée moyenne sync: ${AVG_SYNC_DURATION}s"

# Vitesse moyenne
AVG_SYNC_RATE=$(docker logs "$CONTAINER" --since 24h | grep '^\[SYNC_END.*status=success' | \
    grep -o 'rate=[0-9.]*' | cut -d= -f2 | \
    awk '{sum+=$1; count++} END {if(count>0) printf "%.2f", sum/count; else print "N/A"}')
echo "   Vitesse moyenne: ${AVG_SYNC_RATE} torrents/s"

echo ""

# État système
echo "🔧 ÉTAT SYSTÈME"
CONTAINER_STATUS=$(docker ps --filter "name=^${CONTAINER}$" --format "{{.Status}}")
if [ -n "$CONTAINER_STATUS" ]; then
    echo "   Conteneur: ✅ $CONTAINER_STATUS"
else
    echo "   Conteneur: ❌ Arrêté"
fi

# Dernière activité
LAST_LOG=$(docker logs "$CONTAINER" | tail -1)
if [ -n "$LAST_LOG" ]; then
    echo "   Dernière activité: $(echo "$LAST_LOG" | cut -c1-60)..."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 Astuce: Pour plus de détails, utilisez les commandes du guide LOGS_ANALYSIS.md"
