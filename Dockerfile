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
    && rm -rf /var/lib/apt/lists/*

# Création utilisateur non-root
RUN useradd -u 1000 -d /app -s /bin/bash redriva

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
    # Copier l'exemple vers le fichier de config s'il n'existe pas \
    cp ./config/config.example.json ./config/config.json && \
    # Rendre le script d'entrée exécutable \
    chmod +x ./docker-entrypoint.sh && \
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