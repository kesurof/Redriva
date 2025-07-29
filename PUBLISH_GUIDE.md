# 🚀 Instructions pour publier Redriva sur GitHub

## ✅ Changements appliqués

### Fichiers de sécurité créés :
- `.gitignore` - Protège les fichiers sensibles
- `config/rd_token.conf.example` - Modèle pour le token
- `.env.example` - Modèle pour les variables d'environnement
- `SECURITY.md` - Politique de sécurité
- `setup.sh` - Script de configuration automatique

### Fichiers de projet créés :
- `requirements.txt` - Dépendances Python
- `LICENSE` - Licence MIT
- `CONTRIBUTING.md` - Guide de contribution

### Code modifié :
- `src/main.py` - Support des fichiers .env
- `README.md` - Instructions mises à jour

## 🔒 Fichiers protégés (ignorés par Git)

Ces fichiers ne seront JAMAIS envoyés sur GitHub :
- `config/rd_token.conf` (votre vrai token)
- `.env` (vos variables d'environnement)
- `data/` (votre base de données locale)
- `__pycache__/` et autres fichiers temporaires

## 📤 Publier sur GitHub

### 1. Vérifier que vos fichiers sensibles sont bien protégés
```bash
cd /home/kesurof/Projet_Gihtub/Redriva

# Vérifier ce qui sera envoyé (ne doit PAS inclure vos tokens)
git status
git add .
git status
```

### 2. Premier commit
```bash
git add .
git commit -m "feat: Initial release of Redriva - Real-Debrid torrent sync tool

- Async torrent synchronization with Real-Debrid API
- Multiple sync modes (fast, smart, torrents-only)
- SQLite database for local storage
- Quota management and retry logic
- Environment-based configuration
- Security-first approach with .gitignore protection"
```

### 3. Créer le repo sur GitHub
1. Allez sur https://github.com
2. Cliquez sur "New repository"
3. Nom : `Redriva`
4. Description : "Python tool to sync Real-Debrid torrents to local SQLite database"
5. Public
6. Ne pas créer README (vous en avez déjà un)

### 4. Pousser vers GitHub
```bash
git remote add origin https://github.com/VOTRE-USERNAME/Redriva.git
git branch -M main
git push -u origin main
```

## 🎯 Test final avant publication

Testez que votre configuration fonctionne :
```bash
# Test rapide
python src/main.py --stats

# Si ça marche, vous êtes prêt !
```

## 📋 Checklist finale

- [ ] `.gitignore` créé et fonctionnel
- [ ] Fichiers `.example` créés
- [ ] README mis à jour avec instructions sécurisées
- [ ] Token réel NOT dans Git (vérifier avec `git status`)
- [ ] Code testé localement
- [ ] Repository GitHub créé

## 🚀 Après publication

Vos utilisateurs pourront installer Redriva avec :
```bash
git clone https://github.com/VOTRE-USERNAME/Redriva.git
cd Redriva
./setup.sh
```

Et vous pourrez continuer à développer localement sans exposer vos données !
