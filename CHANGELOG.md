# Changelog - Redriva

## v3.0.0 - Interface DataTable et Token Simplifié (30 juillet 2025)

### 🚀 **Révolution de l'Interface Web**
- **DataTable Moderne** : Remplacement de la table statique par une interface DataTable dynamique
- **Actions Real-Debrid** : Nouvelles actions contextuelles (Supprimer, Réinsérer, Lecture)
- **UX/UI Modernisée** : Design responsive avec statistiques visuelles et notifications

### 🔧 **Simplification Token**
- **Configuration Unique** : Plus qu'une seule méthode via `config/.env`
- **Setup Simplifié** : Script d'installation automatisé
- **Sécurité Renforcée** : Token centralisé et sécurisé

### ✨ **Nouvelles Fonctionnalités**

#### Interface DataTable
- 📊 **Pagination Serveur** : Gestion de milliers de torrents sans latence
- 🔍 **Filtres Avancés** : Statut, taille, recherche textuelle en temps réel  
- 🎨 **Design Responsive** : Interface adaptée mobile/tablette/desktop
- 📈 **Statistiques Visuelles** : Cartes avec gradients et indicateurs temps réel

#### Actions Real-Debrid
- 🗑️ **Supprimer** : Suppression directe des torrents via API Real-Debrid
- ↻ **Réinsérer** : Nouvelle tentative automatique pour torrents en erreur
- 🎬 **Streaming** : Modal avec liens de lecture directe et téléchargement

#### Système Notifications
- 🔔 **Toast Messages** : Notifications contextuelles pour toutes les actions
- ⚡ **Feedback Temps Réel** : Confirmation visuelle immédiate
- 🎯 **Messages Typés** : Succès, erreur, info, warning avec couleurs

### 🌐 **Nouvelles API REST**
```http
POST /api/torrent/delete/{id}    # Supprimer un torrent
POST /api/torrent/reinsert/{id}  # Réinsérer un torrent  
GET  /api/torrent/stream/{id}    # Liens de streaming
```

### 📱 **Amélioration UX**
- **Navigation Intuitive** : Boutons d'action contextuels selon le statut
- **Recherche Instantanée** : Filtrage en temps réel sans rechargement
- **Indicateurs Visuels** : Badges de statut colorés et barres de progression
- **Responsive Design** : Interface optimisée pour tous les écrans

### 🏗️ **Architecture Technique**
- **SQLite Optimisé** : Jointures optimisées entre `torrents` et `torrent_details`
- **AJAX Asynchrone** : Chargement dynamique sans rechargement de page
- **Cache Intelligent** : Réduction des requêtes réseau
- **Gestion d'Erreurs** : Retry automatique et messages explicites

### 🔧 **Configuration Simplifiée**

**AVANT (3 méthodes complexes)** :
```bash
export RD_TOKEN="token"  # Méthode 1
echo "token" > config/rd_token.conf  # Méthode 2  
echo "RD_TOKEN=token" > .env  # Méthode 3
```

**MAINTENANT (1 méthode unique)** :
```bash
cp config/.env.example config/.env
nano config/.env  # RD_TOKEN=votre_token
```

### 📊 **Métriques de Performance**
- ✅ **Tests Interface** : 2/2 pages opérationnelles
- ✅ **Tests API** : 3/3 endpoints fonctionnels
- ✅ **Base de Données** : 4429+ torrents accessibles
- ✅ **Actions Real-Debrid** : Toutes opérationnelles
- ✅ **Temps de Chargement** : < 2 secondes même avec milliers d'entrées

### 🚀 **Guide Migration**
1. **Sauvegarde Token** : Noter votre token Real-Debrid actuel
2. **Mise à Jour** : `git pull origin main`
3. **Configuration** : `./setup.sh` (configuration automatique)
4. **Test** : `python test_interface.py` (validation complète)
5. **Démarrage** : `python src/web.py` (interface modernisée)

### 🎯 **Cas d'Usage Nouveaux**
- **Nettoyage Erreurs** : Filtrer + actions par lot sur torrents défaillants
- **Streaming Direct** : Accès immédiat aux liens de lecture pour torrents téléchargés
- **Monitoring Visuel** : Tableau de bord avec statistiques temps réel
- **Gestion Mobile** : Interface utilisable sur smartphone/tablette

---

## v2.0.0 - Réorganisation architecturale (29 juillet 2025)

### 🏗️ **Architecture repensée**
- **Organisation modulaire** : Code réorganisé en 9 sections logiques avec séparateurs visuels
- **Documentation enrichie** : Chaque fonction documentée avec exemples et cas d'usage
- **Navigation optimisée** : Table des matières et structure claire pour maintenance

### 📚 **Sections du code**
1. **IMPORTS ET CONFIGURATION** : Setup global et variables d'environnement
2. **UTILITAIRES ET HELPERS** : Fonctions de formatage et conversion
3. **BASE DE DONNÉES** : Gestion SQLite et structure données
4. **API REAL-DEBRID** : Communication API et authentification
5. **SYNCHRONISATION** : Moteurs de sync optimisés
6. **STATISTIQUES ET ANALYTICS** : Métriques et analyses
7. **DIAGNOSTIC ET MAINTENANCE** : Diagnostic automatique des erreurs
8. **INTERFACE UTILISATEUR** : Menu interactif et guides
9. **POINT D'ENTRÉE PRINCIPAL** : Orchestration et arguments CLI

### ✨ **Améliorations**
- ✅ **Code plus lisible** : Séparateurs visuels et organisation logique
- ✅ **Maintenance facilitée** : Structure optimisée pour Claude/Copilot
- ✅ **Documentation inline** : Explications détaillées pour chaque fonction
- ✅ **Navigation rapide** : Sections numérotées avec table des matières
- ✅ **Évolutivité** : Architecture prête pour ajouts futurs

### 🔧 **Compatibilité**
- ✅ **Fonctionnalités préservées** : Toutes les fonctions existantes maintenues
- ✅ **Arguments identiques** : Aucun changement dans l'utilisation
- ✅ **Performance identique** : Aucun impact sur les performances
- ✅ **Base de données** : Structure et données inchangées

### 📁 **Fichiers modifiés**
- `src/main.py` : Réorganisé avec nouvelle architecture
- `README.md` : Documentation mise à jour avec architecture
- `src/main_old_backup.py` : Sauvegarde de l'ancienne version

### 🎯 **Objectifs atteints**
- **Maintenabilité** : Code organisé par responsabilité
- **Lisibilité** : Structure claire avec documentation
- **Évolutivité** : Base solide pour développements futurs
- **Compatibilité** : Aucune rupture avec l'existant

---

**Note** : Cette réorganisation prépare Redriva pour une maintenance long terme via Claude/Copilot tout en conservant la simplicité d'un fichier unique.
