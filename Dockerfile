FROM python:3.11-slim

# Build arguments
ARG BUILDTIME
ARG VERSION=dev

# Labels pour SSDV2
LABEL maintainer="Kesurof"
LABEL description="Redriva - Gestionnaire Real-Debrid"
LABEL version="2.0"
LABEL org.opencontainers.image.source="https://github.com/kesurof/Redriva"
LABEL org.opencontainers.image.ref.name="ssdv2"
LABEL org.opencontainers.image.title="redriva-ssdv2"
LABEL org.opencontainers.image.created="${BUILDTIME}"
LABEL org.opencontainers.image.revision="${VERSION}"
LABEL ssdv2.category="media"
LABEL ssdv2.subcategory="downloader"
LABEL ssdv2.tags="real-debrid,torrent,media"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Variables de configuration (vides par défaut, définies au runtime)
# Utilisez -e RD_TOKEN="votre_token" lors du docker run
ENV RD_TOKEN="" \
    SONARR_URL="" \
    SONARR_API_KEY="" \
    RADARR_URL="" \
    RADARR_API_KEY=""

# Installation dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Création utilisateur non-root
RUN useradd -u 1000 -d /app -s /bin/bash redriva && \
    echo "redriva ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Configuration de l'application
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code et configuration
COPY src/ ./src/
COPY config/config.example.json ./config/config.example.json
COPY docker-entrypoint.sh ./docker-entrypoint.sh

# Création des répertoires et configuration initiale
RUN mkdir -p data medias config && \
    cat > ./config/config.example.json << 'EOF'
{
  "token": "",
  "setup_completed": false,
  "auto_sync": true,
  "sync_interval": 300,
  "database_path": "/app/data/redriva.db",
  "sonarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "radarr": {
    "enabled": false,
    "url": "",
    "api_key": ""
  },
  "symlink": {
    "enabled": true,
    "media_path": "/app/medias",
    "workers": 4,
    "sonarr_enabled": false,
    "sonarr_url": "",
    "sonarr_api_key": "",
    "radarr_enabled": false,
    "radarr_url": "",
    "radarr_api_key": ""
  }
}
EOF

# Copier l'exemple vers le fichier de config et configurer les permissions
RUN cp ./config/config.example.json ./config/config.json && \
    chmod +x ./docker-entrypoint.sh && \
    chmod 755 /app/data /app/config /app/medias && \
    chown -R redriva:redriva /app

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Port
EXPOSE 5000

# Utilisateur non-root
USER redriva

# Point d'entrée et commande par défaut
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "src/web.py"]