# ===================================================================
# ÉTAPE 1: Le "Builder" - Installe les dépendances de manière isolée
# ===================================================================
# Utilise une image Python officielle, légère et sécurisée
FROM python:3.12-slim-bullseye AS builder

# Définit les variables d'environnement pour une exécution Python propre
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# Copie uniquement le fichier des dépendances pour optimiser le cache Docker.
# Docker ne réexécutera cette étape que si requirements.txt change.
COPY requirements.txt .

# Installe les dépendances dans un répertoire "wheels" dédié.
# Cela pré-compile les paquets pour une installation plus rapide dans l'image finale.
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ===================================================================
# ÉTAPE 2: L'Image Finale - Légère, sécurisée et prête à l'emploi
# ===================================================================
FROM python:3.12-slim-bullseye

# Définit les variables d'environnement pour une exécution Python propre
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installe wget pour les health checks et nettoie le cache
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

# Crée un groupe et un utilisateur système dédiés pour l'application.
# Exécuter en tant que non-root est une pratique de sécurité essentielle.
RUN addgroup --system app && adduser --system --group app

# Copie les dépendances pré-compilées depuis l'étape "builder"
COPY --from=builder /wheels /wheels

# Installe les dépendances depuis les wheels. C'est plus rapide et ne
# nécessite pas d'outils de compilation dans l'image finale, la gardant légère.
RUN pip install --no-cache /wheels/*

# Définit le répertoire de travail pour le code de l'application
WORKDIR /app

# Crée les répertoires nécessaires avec les bonnes permissions
RUN mkdir -p /app/data /app/config && chown -R app:app /app

# Copie le code source de l'application dans le conteneur
COPY . .

# Attribue la propriété de tous les fichiers à l'utilisateur "app"
RUN chown -R app:app /app

# Bascule vers l'utilisateur non-root "app"
USER app

# Expose le port 5000, sur lequel Gunicorn écoutera les connexions
EXPOSE 5000

# Définit les valeurs par défaut pour Gunicorn
ENV GUNICORN_WORKERS=2
ENV GUNICORN_TIMEOUT=120
ENV GUNICORN_KEEPALIVE=5

# Commande par défaut pour lancer l'application au démarrage du conteneur.
# Utilise Gunicorn, un serveur WSGI robuste pour la production.
# 'src.web:app' signifie : dans le dossier 'src', trouve le fichier 'web.py',
# et à l'intérieur, utilise l'objet Flask nommé 'app'.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} --keep-alive ${GUNICORN_KEEPALIVE} --access-logfile - --error-logfile - src.web:app"]