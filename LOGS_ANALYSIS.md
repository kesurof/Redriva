# 📊 Guide d'Analyse des Logs Structurés Redriva

## 🎯 Vue d'ensemble

Redriva intègre maintenant un système de logs structurés qui permet un monitoring et une analyse faciles via `docker logs`. Chaque événement important est tagué avec des métadonnées exploitables.

## 🔧 Format des Logs Structurés

```
[TAG_NAME key=value key2=value2 ...]
```

**Exemples :**
```
[SYNC_START mode=smart]
[SYNC_END mode=smart status=success torrents=4321 details=60 duration=25.67s rate=4.87/s]
[HEALTH_CHECK_END checked=100 errors=3 duration=12.45s rate=8.03/s]
```

## 🚀 Types d'Événements Disponibles

### Synchronisation
- `SYNC_START` - Démarrage d'une synchronisation
- `SYNC_PHASE_START/END` - Phases individuelles (mode smart uniquement)
- `SYNC_PART` - Étapes intermédiaires
- `SYNC_END` - Fin de synchronisation
- `SYNC_ABORT` - Synchronisation annulée
- `SYNC_TRIGGER` - Déclenchement depuis l'interface web

### Base de Données
- `DB_CHECK_START/END` - Vérification/initialisation de la base
- `CLEAN_START/END` - Nettoyage des torrents supprimés
- `STATS_REFRESH_START/END` - Rafraîchissement des statistiques

### Opérations sur Torrents
- `TORRENT_DETAIL_START/END` - Récupération détails d'un torrent
- `TORRENT_DELETE_START/END` - Suppression d'un torrent
- `TORRENT_REINSERT_START/END` - Réinsertion d'un torrent

### Suppression en Masse
- `BATCH_DELETE_START` - Début suppression batch
- `BATCH_DELETE_PROGRESS` - Progression
- `BATCH_DELETE_END` - Fin suppression batch

### Vérification de Santé
- `HEALTH_SINGLE_START/END` - Vérification d'un torrent
- `HEALTH_CHECK_START/END` - Vérification globale (tous torrents)

### Tâches Asynchrones
- `ASYNC_TASK_START/END` - Tâches en arrière-plan

### Nettoyage Avancé
- `UNAVAILABLE_CLEAN_START/END` - Nettoyage fichiers indisponibles
- `CLEAN_TRIGGER/RETURN` - API de nettoyage

## 📋 Commandes d'Analyse Essentielles

### 1. Monitoring en Temps Réel

```bash
# Tous les événements structurés en direct
docker logs -f redriva | egrep '^\[.*\]'

# Synchronisations uniquement
docker logs -f redriva | egrep '^\[(SYNC_|ASYNC_TASK_)'

# Opérations de santé
docker logs -f redriva | egrep '^\[HEALTH_'

# Base de données et nettoyage
docker logs -f redriva | egrep '^\[(DB_|CLEAN_|STATS_)'
```

### 2. Analyse Historique

```bash
# Dernière synchronisation
docker logs redriva | grep '^\[SYNC_END' | tail -1

# Historique des 10 dernières sync
docker logs redriva | grep '^\[SYNC_END' | tail -10

# Synchronisations réussies vs échecs
docker logs redriva | grep '^\[SYNC_END.*status=success' | wc -l
docker logs redriva | grep '^\[SYNC_END.*status=error' | wc -l

# Performance des sync smart (dernières 24h)
docker logs redriva --since 24h | grep '^\[SYNC_END mode=smart'
```

### 3. Détection d'Erreurs

```bash
# Toutes les erreurs récentes
docker logs redriva --since 2h | egrep '^\[.*status=error'

# Erreurs par type
docker logs redriva | grep '^\[SYNC_.*status=error'
docker logs redriva | grep '^\[HEALTH_.*status=error'
docker logs redriva | grep '^\[TORRENT_.*status=error'

# Dernières erreurs avec contexte
docker logs redriva --since 6h | egrep '^\[.*status=error' | tail -5
```

### 4. Analyse de Performance

```bash
# Vitesses de synchronisation (torrents/seconde)
docker logs redriva | grep '^\[SYNC_END' | grep -o 'rate=[0-9.]*' | cut -d= -f2

# Durées des synchronisations
docker logs redriva | grep '^\[SYNC_END' | grep -o 'duration=[0-9.]*s' | cut -d= -f2

# Performance health check
docker logs redriva | grep '^\[HEALTH_CHECK_END' | grep -o 'rate=[0-9.]*'
```

### 5. Statistiques de Contenu

```bash
# Évolution du nombre de torrents
docker logs redriva | grep '^\[SYNC_END' | grep -o 'torrents=[0-9]*' | cut -d= -f2 | tail -10

# Détails récupérés par sync
docker logs redriva | grep '^\[SYNC_END' | grep -o 'details=[0-9]*' | cut -d= -f2

# Nettoyages effectués
docker logs redriva | grep '^\[CLEAN_END' | grep -o 'deleted=[0-9]*' | cut -d= -f2
```

## 🔍 Scripts d'Analyse Avancée

### Script de Résumé Quotidien

```bash
#!/bin/bash
# daily_summary.sh
echo "📊 Résumé Redriva - $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Synchronisations
SYNC_COUNT=$(docker logs redriva --since 24h | grep '^\[SYNC_END' | wc -l)
SYNC_SUCCESS=$(docker logs redriva --since 24h | grep '^\[SYNC_END.*status=success' | wc -l)
echo "🔄 Synchronisations: $SYNC_SUCCESS/$SYNC_COUNT réussies"

# Erreurs
ERROR_COUNT=$(docker logs redriva --since 24h | egrep '^\[.*status=error' | wc -l)
echo "❌ Erreurs détectées: $ERROR_COUNT"

# Health checks
HEALTH_COUNT=$(docker logs redriva --since 24h | grep '^\[HEALTH_CHECK_END' | wc -l)
echo "🏥 Vérifications santé: $HEALTH_COUNT"

# Nettoyages
CLEAN_COUNT=$(docker logs redriva --since 24h | grep '^\[CLEAN_END' | wc -l)
echo "🧹 Nettoyages: $CLEAN_COUNT"

# Dernière activité
LAST_SYNC=$(docker logs redriva | grep '^\[SYNC_END' | tail -1)
echo "🕐 Dernière sync: $LAST_SYNC"
```

### Script de Monitoring Continu

```bash
#!/bin/bash
# monitor.sh
echo "🔍 Monitoring Redriva en temps réel..."
echo "Appuyez sur Ctrl+C pour arrêter"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker logs -f redriva | while IFS= read -r line; do
    if echo "$line" | grep -q '^\[SYNC_START'; then
        echo "🚀 $(date '+%H:%M:%S') - SYNC DÉMARRÉE: $line"
    elif echo "$line" | grep -q '^\[SYNC_END.*status=success'; then
        echo "✅ $(date '+%H:%M:%S') - SYNC RÉUSSIE: $line"
    elif echo "$line" | grep -q '^\[.*status=error'; then
        echo "❌ $(date '+%H:%M:%S') - ERREUR: $line"
    elif echo "$line" | grep -q '^\[HEALTH_CHECK_END'; then
        echo "🏥 $(date '+%H:%M:%S') - HEALTH CHECK: $line"
    elif echo "$line" | grep -q '^\[CLEAN_END'; then
        echo "🧹 $(date '+%H:%M:%S') - NETTOYAGE: $line"
    fi
done
```

## 📈 Exemples de Métriques Exploitables

### KPIs de Performance
```bash
# Temps moyen de synchronisation smart (dernière semaine)
docker logs redriva --since 7d | grep '^\[SYNC_END mode=smart' | \
  grep -o 'duration=[0-9.]*' | cut -d= -f2 | \
  awk '{sum+=$1; count++} END {print "Durée moyenne:", sum/count "s"}'

# Efficacité du health check (erreurs 503 détectées)
docker logs redriva | grep '^\[HEALTH_CHECK_END' | \
  awk -F'[= ]' '{for(i=1;i<=NF;i++) if($i=="errors") print $(i+1)}' | \
  awk '{sum+=$1; count++} END {print "Moyenne erreurs 503 par check:", sum/count}'
```

### Détection d'Anomalies
```bash
# Sync prenant plus de 5 minutes
docker logs redriva | grep '^\[SYNC_END' | \
  grep -o 'duration=[0-9.]*' | cut -d= -f2 | \
  awk '$1 > 300 {print "⚠️ Sync lente:", $1 "s"}'

# Taux d'erreur élevé
docker logs redriva --since 24h | grep '^\[SYNC_END' | \
  awk 'END {total=NR} /status=error/ {errors++} 
       END {rate=errors/total*100; if(rate>10) print "⚠️ Taux erreur élevé:", rate "%"}'
```

## 🎛️ Intégration avec des Outils de Monitoring

### Prometheus/Grafana
```bash
# Export de métriques pour Prometheus
docker logs redriva --since 1h | grep '^\[SYNC_END' | \
  awk -F'[= ]' '
  {
    for(i=1;i<=NF;i++) {
      if($i=="mode") mode=$(i+1)
      if($i=="torrents") torrents=$(i+1)
      if($i=="duration") duration=$(i+1)
    }
  }
  END {
    print "redriva_sync_duration_seconds{mode=\"" mode "\"} " duration
    print "redriva_torrents_total{mode=\"" mode "\"} " torrents
  }'
```

### Alerting
```bash
# Détection d'absence de sync (> 6h)
LAST_SYNC_TIME=$(docker logs redriva | grep '^\[SYNC_END' | tail -1 | grep -o '[0-9-]* [0-9:]*')
if [ -n "$LAST_SYNC_TIME" ]; then
    LAST_EPOCH=$(date -d "$LAST_SYNC_TIME" +%s)
    CURRENT_EPOCH=$(date +%s)
    DIFF=$((CURRENT_EPOCH - LAST_EPOCH))
    if [ $DIFF -gt 21600 ]; then
        echo "🚨 ALERTE: Aucune synchronisation depuis $((DIFF/3600))h"
    fi
fi
```

## 🎯 Cas d'Usage Pratiques

### 1. Debug d'une Sync Lente
```bash
# Analyser la dernière sync smart en détail
docker logs redriva | grep -A 20 -B 5 '^\[SYNC_START mode=smart' | tail -25
```

### 2. Audit de Sécurité
```bash
# Vérifier les suppressions de torrents
docker logs redriva | grep '^\[TORRENT_DELETE_END.*status=success' | wc -l
```

### 3. Optimisation des Performances
```bash
# Identifier les goulots d'étranglement
docker logs redriva | grep '^\[SYNC_PHASE_END' | \
  grep -o 'duration=[0-9.]*s' | sort -n | tail -5
```

## 🔗 Intégration Docker Compose

Ajoutez à votre monitoring stack :

```yaml
# docker-compose.monitoring.yml
services:
  log-analyzer:
    image: alpine
    volumes:
      - ./scripts:/scripts
    command: sh -c "while true; do /scripts/daily_summary.sh; sleep 3600; done"
    depends_on:
      - redriva
```

---

**Note :** Tous ces logs sont maintenant disponibles grâce à l'instrumentation complète du code avec des événements `log_event()` structurés. Le système est prêt pour une utilisation en production avec monitoring avancé.
