# Redriva - Votre Gestionnaire de Torrents Real-Debrid

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.x-green?style=for-the-badge&logo=flask)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

Redriva est un outil puissant doté d'une interface web élégante pour gérer votre collection de torrents Real-Debrid. Il synchronise vos données localement dans une base de données SQLite, vous offrant une vue rapide, des statistiques détaillées et des outils de maintenance que l'interface native de Real-Debrid ne propose pas.

<!-- Suggestion: Remplacez par une vraie capture d'écran -->
![Dashboard Redriva](https://i.imgur.com/8aJgP0d.png) 

## ✨ Fonctionnalités Principales

### 🖥️ Interface Web Intuitive
- **Dashboard Statistique** : Visualisez en un coup d'œil l'état de votre collection (total, erreurs, actifs, etc.).
- **Liste de Torrents Paginée** : Naviguez facilement à travers des milliers de torrents avec filtres, tri et recherche.
- **Actions Directes** : Supprimez, réinsérez ou consultez les détails de n'importe quel torrent directement depuis l'interface.
- **Suppression en Masse** : Sélectionnez et supprimez plusieurs torrents en une seule fois.
- **Liens de Streaming & Téléchargement** : Accédez facilement aux liens de vos fichiers.

### ⚙️ Moteur de Synchronisation Avancé (CLI)
- **Modes de Sync Multiples** :
  - `--sync-smart`: Mode intelligent pour les mises à jour quotidiennes (rapide et efficace).
  - `--sync-fast`: Synchronisation complète optimisée pour la première utilisation.
  - `--torrents-only`: Vue d'ensemble ultra-rapide de vos torrents.
- **Statistiques Détaillées** : Obtenez une analyse complète de votre collection en ligne de commande.
- **Diagnostic d'Erreurs** : Identifiez et obtenez des suggestions pour les torrents problématiques.
- **Menu Interactif** : Pas besoin de mémoriser les commandes, laissez-vous guider.

## 🚀 Installation

1.  **Clonez le dépôt :**
    ```bash
    git clone https://github.com/kesurof/Redriva.git
    cd Redriva
    ```

2.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

## 🛠️ Configuration

1.  **Créez votre fichier d'environnement :**
    ```bash
    cp .env.example .env
    ```

2.  **Ajoutez votre token Real-Debrid** dans le fichier `.env` que vous venez de créer :
    ```env
    RD_TOKEN=VOTRE_TOKEN_REAL_DEBRID
    ```
    > Vous pouvez obtenir votre token depuis votre [page de profil Real-Debrid](https://real-debrid.com/apitoken).

## � Installation Docker (Recommandée)

Docker offre la solution la plus simple et la plus fiable pour faire fonctionner Redriva.

### Installation Rapide avec Docker

1.  **Clonez le dépôt :**
    ```bash
    git clone https://github.com/kesurof/Redriva.git
    cd Redriva
    ```

2.  **Configuration automatique :**
    ```bash
    ./docker-helper.sh setup
    ```

3.  **Modifiez votre token** dans `config/.env` :
    ```bash
    nano config/.env
    # Remplacez 'votre_token_ici' par votre vrai token Real-Debrid
    ```

4.  **Démarrez Redriva :**
    ```bash
    ./docker-helper.sh start
    ```

L'application sera accessible sur `http://localhost:5000` 🎉

### Commandes Docker Utiles

| Commande | Description |
|----------|-------------|
| `./docker-helper.sh start` | Démarre Redriva |
| `./docker-helper.sh stop` | Arrête Redriva |
| `./docker-helper.sh restart` | Redémarre Redriva |
| `./docker-helper.sh logs` | Affiche les logs en temps réel |
| `./docker-helper.sh status` | Vérifiez l'état des conteneurs |
| `./docker-helper.sh update` | Met à jour vers la dernière version |

### Installation Docker Manuelle

Si vous préférez utiliser docker-compose directement :

```bash
# Après configuration du token dans config/.env
docker-compose up -d

# Pour voir les logs
docker-compose logs -f

# Pour arrêter
docker-compose down
```

## �💡 Utilisation

### Lancer l'Interface Web (Recommandé)

1.  **Effectuez une première synchronisation** pour remplir votre base de données locale. Le mode `smart` est parfait pour commencer.
    ```bash
    python src/main.py --sync-smart
    ```

2.  **Lancez le serveur web :**
    ```bash
    python src/web.py
    ```

3.  Ouvrez votre navigateur et allez à l'adresse **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

### Utiliser en Ligne de Commande

-   **Pour le menu interactif (le plus simple) :**
    ```bash
    python src/main.py
    ```
-   **Pour une synchronisation intelligente :**
    ```bash
    python src/main.py --sync-smart
    ```
-   **Pour afficher les statistiques :**
    ```bash
    python src/main.py --stats
    ```

## 💻 Stack Technique

-   **Backend** : Python, Flask, aiohttp
-   **Base de données** : SQLite
-   **Frontend** : HTML, CSS, JavaScript (sans framework)
-   **Containerisation** : Docker, Docker Compose

## 📄 Licence

Ce projet est distribué sous la licence MIT. Voir le fichier `LICENSE` pour plus de détails.