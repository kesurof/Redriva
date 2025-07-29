# 🌐 Redriva Web Interface - Guide Complet

Documentation complète de l'interface web interactive de Redriva

## 📖 Table des Matières

1. [Introduction](#-introduction)
2. [Démarrage Rapide](#-démarrage-rapide)
3. [Dashboard Principal](#-dashboard-principal)
4. [Navigation et Fonctionnalités](#-navigation-et-fonctionnalités)
5. [Actions de Synchronisation](#-actions-de-synchronisation)
6. [Pages de Détail](#-pages-de-détail)
7. [Interface Utilisateur](#-interface-utilisateur)
8. [Troubleshooting](#-troubleshooting)
9. [Configuration Avancée](#-configuration-avancée)

---

## 🎯 Introduction

L'interface web de Redriva offre une expérience utilisateur moderne et interactive pour gérer vos torrents Real-Debrid. Elle transforme les données de votre base SQLite en interface graphique intuitive avec dashboard interactif, statistiques en temps réel et actions de synchronisation simplifiées.

### Fonctionnalités Clés
- 📊 **Dashboard interactif** avec cartes statistiques cliquables
- 🔄 **Synchronisation en un clic** avec feedback temps réel
- 📋 **Console de logs** intégrée pour monitoring
- 🔍 **Navigation intelligente** avec filtres et recherche
- 📱 **Design responsive** adapté mobile et desktop
- 🎨 **Interface moderne** avec animations et notifications

---

## 🚀 Démarrage Rapide

### Prérequis
- Python 3.7+
- Base de données Redriva initialisée (via `python src/main.py --sync-smart`)
- Token Real-Debrid configuré

### Lancement du Serveur Web

```bash
# Méthode 1 : Script direct
python src/web.py

# Méthode 2 : Via le menu principal
python src/main.py
# Puis choisir l'option "Interface Web"

# Méthode 3 : Via setup.sh
./setup.sh
# L'interface web sera proposée après configuration
```

### Accès à l'Interface
- **URL locale :** http://127.0.0.1:5000
- **Arrêt du serveur :** `Ctrl+C` ou `./stop_web.sh`

---

## 📊 Dashboard Principal

Le dashboard est le cœur de l'interface web, offrant une vue d'ensemble complète de votre collection Real-Debrid.

### Cartes Statistiques Interactives

#### 📁 Carte "Torrents"
- **Fonction :** Affiche le nombre total de torrents dans votre base
- **Interaction :** Clic → Vue complète de tous les torrents
- **Indicateur :** Nombre total depuis la dernière synchronisation

#### 📋 Carte "Détails" 
- **Fonction :** Pourcentage de couverture des détails complets
- **Interaction :** Clic → Modal d'informations sur la couverture
- **Calcul :** `(torrents avec détails / total torrents) × 100`

#### ⬇️ Carte "Actifs"
- **Fonction :** Torrents en cours de traitement (downloading, queued, waiting, etc.)
- **Interaction :** Clic → Liste filtrée des torrents actifs
- **Statuts inclus :** downloading, queued, waiting_files_selection, magnet_conversion, uploading, compressing, waiting

#### ❌ Carte "Erreurs"
- **Fonction :** Torrents nécessitant intervention (errors, timeouts, etc.)
- **Interaction :** Clic → Liste filtrée des torrents en erreur
- **Statuts inclus :** error, magnet_error, virus, dead, timeout, hoster_unavailable

### Effets Visuels
- **Hover :** Élévation de la carte avec ombre portée
- **Animation :** Flèche directionnelle qui s'anime au survol
- **Feedback :** Cursor pointer pour indiquer l'interactivité

---

## 🔄 Actions de Synchronisation

Interface simplifiée pour déclencher les différents types de synchronisation avec confirmations et logs en temps réel.

### 🧠 Synchronisation Intelligente
```
Bouton : "Sync intelligent"
Description : Analyse et traite selon les priorités
Fonction : Équivalent à --sync-smart
Temps estimé : 30s - 2 minutes
```
- Analyse les changements nécessaires
- Mise à jour des torrents actifs et en erreur
- Mode recommandé pour usage quotidien

### 🚀 Synchronisation Rapide
```
Bouton : "Sync rapide"  
Description : Traitement accéléré des nouveautés
Fonction : Équivalent à --sync-fast
Temps estimé : 7-10 minutes
```
- Synchronisation complète optimisée
- Pool de connexions avec concurrence dynamique
- Reprise automatique en cas d'interruption

### 📋 Torrents Uniquement
```
Bouton : "Torrents uniquement"
Description : Met à jour la liste des torrents
Fonction : Équivalent à --torrents-only  
Temps estimé : 10-30 secondes
```
- Synchronise uniquement la liste de base
- Parfait pour découverte rapide des nouveautés
- Pas de récupération des détails complets

### 🔄 Retry Erreurs
```
Bouton : "Retry erreurs"
Description : Retente les torrents en échec
Fonction : Équivalent à --details-only --status error
Temps estimé : Variable selon erreurs
```
- Retente uniquement les torrents en erreur
- Analyse automatique des types d'erreurs
- Retry intelligent selon le type de problème

### Système de Confirmation
Chaque action déclenche une **modal de confirmation** avec :
- Titre descriptif de l'action
- Message d'avertissement si nécessaire
- Boutons "Confirmer" / "Annuler"
- Fermeture possible avec `Escape`

---

## 🔍 Navigation et Fonctionnalités

### Navigation Rapide
Section dédiée avec liens directs vers les vues filtrées :

#### 📁 Tous les Torrents
- **Destination :** `/torrents`
- **Contenu :** Liste complète paginée de tous les torrents
- **Badge :** Nombre total de torrents

#### ❌ Torrents en Erreur
- **Destination :** `/torrents?status=error`
- **Contenu :** Torrents nécessitant intervention
- **Badge :** Nombre d'erreurs détectées
- **Couleur :** Rouge (danger)

#### ⬇️ En Cours
- **Destination :** `/torrents?status=downloading`
- **Contenu :** Téléchargements et traitements actifs
- **Badge :** Nombre de torrents actifs
- **Couleur :** Orange (warning)

#### ✅ Téléchargés
- **Destination :** `/torrents?status=downloaded`
- **Contenu :** Torrents complètement téléchargés
- **Badge :** Dynamique selon la base
- **Couleur :** Vert (success)

### Répartition par Statut
Tableau moderne avec visualisation des données :

| Colonne | Description |
|---------|-------------|
| **Statut** | Badge coloré avec nom du statut |
| **Nombre** | Compteur de torrents pour ce statut |
| **Pourcentage** | Calcul automatique sur le total |
| **Visualisation** | Barre de progression proportionnelle |

---

## 📋 Console de Logs Interactive

### Fonctionnalités
- **Logs temps réel** des actions exécutées
- **Auto-scroll automatique** (désactivable)
- **Coloration syntaxique** par type de log
- **Timestamps** automatiques
- **Contrôles intégrés** (clear, auto-scroll toggle)

### Types de Logs
```css
📘 INFO    - Informations générales (bleu)
✅ SUCCESS - Opérations réussies (vert)  
⚠️ WARNING - Avertissements (orange)
❌ ERROR   - Erreurs rencontrées (rouge)
```

### Contrôles
- **📌 Auto-scroll :** Active/désactive le défilement automatique
- **🗑️ Effacer :** Vide la console (avec confirmation)
- **Statistiques :** Compteur d'entrées et horodatage

---

## 📱 Interface Utilisateur

### Design System

#### Couleurs Principales
```css
Primary (Bleu):    #007bff - Actions principales
Success (Vert):    #28a745 - Opérations réussies
Warning (Orange):  #ffc107 - Avertissements
Danger (Rouge):    #dc3545 - Erreurs et suppression
Info (Cyan):       #17a2b8 - Informations
```

#### Typography
```css
Titres:     Poids 600-700, tailles variables
Corps:      Poids 400, 14-16px
Monospace:  Courier New pour logs et données techniques
```

### Composants Interactifs

#### Cartes Statistiques
- **État Normal :** Ombre légère, couleurs de marque
- **État Hover :** Élévation (-2px), ombre accentuée
- **État Actif :** Animation de la flèche directionnelle

#### Boutons d'Action
- **Style :** Design moderne avec bordures et espacement
- **Hover :** Élévation et changement de couleur de bordure
- **Focus :** Outline pour accessibilité

#### Notifications Toast
- **Position :** Coin supérieur droit, empilables
- **Animation :** Slide-in depuis la droite
- **Auto-dismiss :** 5 secondes avec animation slide-out
- **Types :** Success, Error, Info, Warning

### Responsive Design

#### Breakpoints
```css
Mobile:    < 768px  - Layout une colonne
Tablet:    768px+   - Layout deux colonnes  
Desktop:   1024px+  - Layout complet
```

#### Adaptations Mobile
- Cartes statistiques en grille 2×2
- Actions de sync en colonne unique
- Navigation rapide empilée
- Console de logs hauteur réduite

---

## 🛠️ Troubleshooting

### Problèmes Courants

#### Serveur Web ne Démarre Pas
```bash
# Erreur : "Port 5000 already in use"
./stop_web.sh
python src/web.py

# Erreur : "Token not found"
export RD_TOKEN="votre_token"
python src/web.py
```

#### Interface Vide ou Erreurs
```bash
# Vérifier la base de données
python src/main.py --stats

# Si vide, synchroniser
python src/main.py --sync-smart

# Puis relancer le web
python src/web.py
```

#### Statistiques Incorrectes
```bash
# Forcer la mise à jour des constantes
python src/main.py --sync-smart

# Vérifier la cohérence
python src/main.py --stats --compact
```

### Logs de Debug

#### Côté Serveur (Terminal)
```bash
# Logs Flask visibles dans le terminal
[2025-07-29 15:16:04] INFO: Running on http://127.0.0.1:5000
```

#### Côté Client (Navigateur)
```javascript
// Console développeur (F12)
// Logs d'erreurs AJAX, JavaScript, etc.
```

### Performance

#### Optimisations Automatiques
- **Mise en cache** des statistiques (30 secondes)
- **Pagination** automatique des listes
- **Lazy loading** des images et contenus lourds
- **Compression** des réponses JSON

#### Surveillance
```bash
# Monitoring basique via terminal
# CPU, mémoire, requêtes/seconde visibles
```

---

## ⚙️ Configuration Avancée

### Variables d'Environnement Web

```bash
# Port du serveur (défaut: 5000)
export FLASK_PORT=8080

# Mode debug (développement uniquement)
export FLASK_DEBUG=true

# Pagination (éléments par page)
export WEB_PAGE_SIZE=50

# Cache durée (secondes)
export STATS_CACHE_TTL=30
```

### Personnalisation CSS

#### Fichier de Styles Customs
```bash
# Créer un fichier de surcharge
touch src/templates/custom.css

# L'inclure dans base.html
<link rel="stylesheet" href="{{ url_for('static', filename='custom.css') }}">
```

#### Variables CSS Modifiables
```css
:root {
  --primary-color: #007bff;
  --success-color: #28a745;
  --warning-color: #ffc107;
  --danger-color: #dc3545;
  --font-family: 'Segoe UI', system-ui;
}
```

### Sécurité

#### Protection CSRF
```python
# Auto-activée sur toutes les actions POST
# Tokens générés automatiquement
```

#### Rate Limiting
```python
# Limitation automatique des actions de sync
# 1 action par minute par IP
```

#### Validation des Entrées
```python
# Toutes les entrées utilisateur validées
# Protection contre injection SQL/XSS
```

---

## 📈 Métriques et Analytics

### Statistiques Collectées
- **Sessions utilisateur** (durée, pages vues)
- **Actions de synchronisation** (type, durée, succès/échec)
- **Performance serveur** (temps de réponse, mémoire)
- **Erreurs** (fréquence, types, résolution)

### Exportation des Données
```bash
# Export des statistiques en JSON
curl http://127.0.0.1:5000/api/stats/export

# Logs d'activité
tail -f data/webapp.log
```

---

## 🚀 Mise à Jour et Evolution

### Versions Compatibles
- **Python :** 3.7+ (testé jusqu'à 3.11)
- **Flask :** 2.0+ (auto-installé via requirements.txt)
- **Navigateurs :** Chrome 70+, Firefox 65+, Safari 12+

### Roadmap Fonctionnalités
- [ ] **API REST complète** pour intégrations tierces
- [ ] **Système d'utilisateurs** multi-comptes
- [ ] **Notifications push** via WebSocket
- [ ] **Thèmes personnalisables** (sombre, clair, coloré)
- [ ] **Export/Import** de configurations
- [ ] **Scheduling** de synchronisations

### Contributions
Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les guidelines de développement.

---

## 📞 Support et Documentation

### Ressources Utiles
- **Documentation principale :** [README.md](README.md)
- **Guide CLI :** `python src/main.py --help`
- **Changelog :** [CHANGELOG.md](CHANGELOG.md)
- **Sécurité :** [SECURITY.md](SECURITY.md)

### Communauté et Support
- **Issues GitHub :** Pour bugs et demandes de fonctionnalités
- **Discussions :** Pour questions et partage d'expérience
- **Wiki :** Documentation collaborative et exemples

---

## 📝 Conclusion

L'interface web de Redriva transforme la gestion de vos torrents Real-Debrid en expérience moderne et intuitive. Avec son dashboard interactif, ses actions simplifiées et son monitoring en temps réel, elle rend accessible toute la puissance de Redriva via une interface graphique élégante.

**Commencer maintenant :**
```bash
python src/web.py
# Puis ouvrir http://127.0.0.1:5000
```

---

*Dernière mise à jour : Juillet 2025*  
*Version de l'interface web : 2.0 (Interactive Dashboard)*
