# 🔐 Sécurité des Configurations

## ⚠️ Fichiers sensibles

Les fichiers suivants contiennent des informations sensibles et **NE DOIVENT JAMAIS** être commitées dans Git :

- `config/config.json` - Configuration avec tokens et clés API
- `.env*` - Variables d'environnement
- `data/*.db` - Bases de données locales

## 🛡️ Protection mise en place

### .gitignore
Tous les fichiers sensibles sont protégés par `.gitignore` :
```gitignore
config/config.json
config/*.json
!config/config.example.json
.env*
data/
*.db
```

### Fichier d'exemple
- `config/config.example.json` - Template sans données sensibles
- Utilisé automatiquement pour créer `config.json` au premier démarrage

## 🚀 Déploiement sécurisé

### 1. Premier démarrage
```bash
# Le fichier config.json sera créé automatiquement depuis l'exemple
python src/web.py
```

### 2. Configuration via l'interface web
- Accédez à `http://localhost:5000/setup`
- Entrez votre token Real-Debrid
- Configurez Sonarr/Radarr (optionnel)

### 3. Variables d'environnement (recommandé pour production)
```bash
export RD_TOKEN="votre_token_real_debrid"
export SONARR_URL="http://localhost:8989"
export SONARR_API_KEY="votre_clé_sonarr"
export RADARR_URL="http://localhost:7878"
export RADARR_API_KEY="votre_clé_radarr"
```

## 🔍 Vérification

### Avant commit
```bash
# Vérifier qu'aucun fichier sensible n'est tracké
git status
git ls-files | grep -E "(config\.json|\.env)"

# Doit retourner vide (sauf config.example.json)
```

### Historique Git
```bash
# Rechercher d'éventuels tokens dans l'historique
git log --all --full-history -- config/config.json
```

## 🆘 En cas de fuite

### 1. Supprimer immédiatement du tracking
```bash
git rm --cached config/config.json
git commit -m "🔒 Remove sensitive config file"
```

### 2. Nettoyer l'historique (si nécessaire)
```bash
git filter-branch --index-filter 'git rm --cached --ignore-unmatch config/config.json' HEAD
```

### 3. Révoquer les tokens compromis
- Real-Debrid : Générer un nouveau token
- Sonarr/Radarr : Régénérer les clés API

## 📋 Checklist sécurité

- [ ] `config/config.json` dans `.gitignore`
- [ ] `config.example.json` sans données sensibles  
- [ ] Variables d'environnement pour la production
- [ ] Tokens révoqués si compromis
- [ ] Historique Git nettoyé si nécessaire
