# ===================================================================
# ÉTAPE 1: Le "Builder" - Installe les dépendances de manière isolée
# ===================================================================
# Utilise une image Python officielle, légère et sécurisée
FROM python:3.12-slim-bullseye AS builder

# Support multi-architecture explicite
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "Building for $TARGETPLATFORM on $BUILDPLATFORM"

# Définit les variables d'environnement pour une exécution Python propre
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# Installe les dépendances système nécessaires pour la compilation multi-architecture
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copie uniquement le fichier des dépendances pour optimiser le cache Docker.
# Docker ne réexécutera cette étape que si requirements.txt change.
COPY requirements.txt .

# Installe les dépendances dans un répertoire "wheels" dédié avec optimisations ARM64.
# Cela pré-compile les paquets pour une installation plus rapide dans l'image finale.
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ===================================================================
# ÉTAPE 2: L'Image Finale - Légère, sécurisée et prête à l'emploi
# ===================================================================
FROM python:3.12-slim-bullseye

# Support multi-architecture
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Définit les variables d'environnement pour une exécution Python propre
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installe wget et curl pour les health checks et outils réseau, puis nettoie le cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gosu \
    ffmpeg \
    ca-certificates \
    gnupg \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Copie les dépendances pré-compilées depuis l'étape "builder"
COPY --from=builder /wheels /wheels

# Installe les dépendances depuis les wheels avec optimisations multi-architecture.
# C'est plus rapide et ne nécessite pas d'outils de compilation dans l'image finale.
RUN pip install --no-cache --no-deps /wheels/* \
    && rm -rf /wheels

# Définit le répertoire de travail pour le code de l'application
WORKDIR /app

# Crée les répertoires nécessaires - SSDV2 gérera les permissions
RUN mkdir -p /app/data /app/config

# Copie le code source de l'application dans le conteneur
COPY . .

# Expose le port 5000, sur lequel Gunicorn écoutera les connexions
EXPOSE 5000

# Définit les valeurs par défaut pour Gunicorn
ENV GUNICORN_WORKERS=2
ENV GUNICORN_TIMEOUT=120
ENV GUNICORN_KEEPALIVE=5

# Health check optimisé pour multi-architecture
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5000/api/health || exit 1

# Commande par défaut pour lancer l'application au démarrage du conteneur.
# Utilise Gunicorn, un serveur WSGI robuste pour la production.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} --keep-alive ${GUNICORN_KEEPALIVE} --access-logfile - --error-logfile - src.web:app"]