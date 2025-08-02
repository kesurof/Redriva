.PHONY: help setup dev prod logs stop restart status pull update info clean

help: ## Affiche cette aide
	@echo "🏗️ Redriva - Commandes de gestion"
	@echo "================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Configuration initiale
	./setup.sh

dev: ## Démarrage en mode développement
	docker compose up --build

prod: ## Démarrage en production
	docker compose up -d

logs: ## Affichage des logs
	docker compose logs -f

stop: ## Arrêt des conteneurs
	docker compose down

restart: ## Redémarrage
	docker compose restart

status: ## Statut des conteneurs
	docker compose ps

pull: ## Téléchargement de la dernière image
	docker compose pull

update: pull restart ## Mise à jour complète

clean: ## Nettoyage Docker
	@echo "🧹 Nettoyage des images Docker inutilisées..."
	docker image prune -f
	docker volume prune -f
	@echo "✅ Nettoyage terminé"

info: ## Informations système
	@echo "📋 Informations Redriva"
	@echo "======================"
	@echo "🐳 Docker:"
	@docker --version
	@docker compose --version
	@echo ""
	@echo "📦 Images:"
	@docker images ghcr.io/kesurof/redriva --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" 2>/dev/null || echo "Aucune image Redriva trouvée"
	@echo ""
	@echo "🔧 Conteneurs:"
	@docker compose ps
