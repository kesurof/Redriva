# 🚀 Redriva

Redriva est une application web moderne qui simplifie l'accès à vos fichiers Real-Debrid. Interface élégante, gestion automatique et téléchargements en un clic !

## ✨ Fonctionnalités

- 🔗 **Conversion automatique** : Transforme les liens torrents/magnets
- 📁 **Gestionnaire de fichiers** : Parcourez et organisez facilement
- ⬇️ **Téléchargements directs** : Un clic pour télécharger
- 🎯 **Interface moderne** : Design épuré et responsive
- 🔄 **Synchronisation** : Mise à jour automatique de votre bibliothèque
- 🌙 **Mode sombre** : Pour vos sessions nocturnes

## 🛠️ Installation

### Développement (Python)

Pour développer et tester localement :

```bash
# 1. Cloner le projet
git clone https://github.com/kesurof/Redriva.git
cd Redriva

# 2. Configuration initiale
./setup.sh

# 3. Configurer votre token Real-Debrid
nano config/.env
# Remplacez 'votre_token_ici' par votre vrai token

# 4. Lancer en mode développement
./dev.sh
```

L'application sera accessible sur `http://localhost:5000` 🎉

### Production (Docker)

Pour déployer en production :

```bash
# 1. Cloner le projet
git clone https://github.com/kesurof/Redriva.git
cd Redriva

# 2. Configuration initiale
./setup.sh

# 3. Configurer votre token Real-Debrid
nano config/.env
# Remplacez 'votre_token_ici' par votre vrai token

# 4. Lancer avec Docker
docker-compose up -d

# Commandes utiles
docker-compose logs -f    # Voir les logs
docker-compose down       # Arrêter
docker-compose pull       # Mettre à jour
```

L'image Docker est automatiquement construite et disponible sur `ghcr.io/kesurof/redriva:latest`.

## 🔧 Configuration

### Token Real-Debrid

1. Connectez-vous sur [Real-Debrid](https://real-debrid.com)
2. Allez dans **Mon compte** → **Clé API**
3. Copiez votre token
4. Modifiez `config/.env` :
   ```
   REAL_DEBRID_TOKEN=votre_token_ici
   ```

## 📖 Utilisation

1. **Ajout de torrents/magnets** : Collez vos liens dans l'interface
2. **Navigation** : Parcourez vos fichiers par dossiers
3. **Téléchargement** : Clic droit → "Enregistrer sous" ou clic direct
4. **Gestion** : Organisez et supprimez vos téléchargements

## 🏗️ Architecture

- **Backend** : Python Flask avec Real-Debrid API
- **Frontend** : HTML/CSS/JavaScript moderne
- **Base de données** : SQLite pour la synchronisation
- **Déploiement** : Docker avec GitHub Actions CI/CD

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [Real-Debrid](https://real-debrid.com) pour leur excellente API
- La communauté open source pour l'inspiration

---

**⚡ Redriva - Votre passerelle vers Real-Debrid !**
