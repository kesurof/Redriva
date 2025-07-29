# Politique de sécurité

## 🔐 Gestion des tokens et données sensibles

### ⚠️ Important
- **Ne jamais** commiter vos vrais tokens Real-Debrid
- **Ne jamais** partager vos fichiers de configuration personnels
- Utilisez toujours les fichiers `.example` comme modèles

### 🛡️ Fichiers protégés

Les fichiers suivants sont automatiquement ignorés par Git :
- `config/rd_token.conf`
- `.env`
- `data/` (contient votre base de données locale)

### 🚨 En cas de token compromis

Si vous avez accidentellement exposé votre token :
1. Connectez-vous immédiatement sur [Real-Debrid](https://real-debrid.com)
2. Allez dans **Mon compte** → **API**
3. Régénérez un nouveau token
4. Mettez à jour votre configuration locale
5. Vérifiez l'historique Git pour supprimer les traces

### 📧 Signaler une vulnérabilité

Si vous découvrez une faille de sécurité, veuillez :
- Ne pas la divulguer publiquement
- Créer une issue privée ou nous contacter directement
- Nous laisser le temps de corriger avant publication
