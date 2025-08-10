# 🚀 GitHub Actions Workflow

## 📦 Build automatique SSDV2

Ce workflow GitHub Actions construit automatiquement l'image Docker pour SSDV2 :

### 🔄 Déclencheurs
- **Push** sur la branche `ssdv2`
- **Pull Request** vers la branche `ssdv2` 
- **Déclenchement manuel** via l'interface GitHub

### 📋 Étapes du workflow

1. **Checkout** du code source
2. **Setup** Docker Buildx pour multi-platform
3. **Login** vers GitHub Container Registry (GHCR)
4. **Extraction** des métadonnées (tags, labels)
5. **Build & Push** de l'image Docker
6. **Génération** du résumé de déploiement

### 🏷️ Tags générés

- `ghcr.io/kesurof/redriva:ssdv2` (tag principal)
- `ghcr.io/kesurof/redriva:ssdv2-{commit}` (tag par commit)
- `ghcr.io/kesurof/redriva:{branch}` (tag par branche)

### 🏗️ Plateformes supportées

- `linux/amd64` (Intel/AMD)
- `linux/arm64` (ARM64/Apple Silicon)

### 🔧 Configuration requise

Aucune configuration supplémentaire requise ! Le workflow utilise :
- `GITHUB_TOKEN` automatique pour l'authentification
- Cache GitHub Actions pour accélérer les builds
- Métadonnées automatiques depuis Git

### 📈 Monitoring

- ✅ Status du build visible dans l'onglet **Actions**
- 📊 Résumé généré automatiquement
- 🐳 Image disponible dans **Packages**

### 🚀 Utilisation de l'image

```bash
# Pull de l'image
docker pull ghcr.io/kesurof/redriva:ssdv2

# Lancement
docker run -p 5000:5000 -e RD_TOKEN=your_token ghcr.io/kesurof/redriva:ssdv2
```

L'image est **publique** et directement utilisable dans SSDV2 ! 🎯
