# Développement local — Redriva

Ce document explique comment développer et lancer Redriva en local en utilisant le script `dev.sh` fourni dans la racine du projet. L'objectif : isolation totale dans un virtualenv local `./redriva`, usages courants, flags utiles, et dépannage rapide.

## Principes

- Le script `dev.sh` crée (ou réutilise) un virtualenv local `./redriva` et installe les dépendances du fichier `requirements.txt` strictement dans ce venv.
- L'exécution (foreground ou background) utilise le binaire Python du venv et s'effectue dans un environnement nettoyé (`env -i`). Cela évite toute dépendance ou contamination par d'autres venvs présents sur le système.
- Par défaut, le venv n'est pas recréé. Utilisez l'option `--recreate-venv` (alias `-r`) pour forcer la suppression et la recréation du venv.

## Fichiers clés

- `dev.sh` — script d'aide pour développement et exécution locale.
- `requirements.txt` — dépendances Python installées dans `./redriva`.
- `./redriva/` — virtualenv local créé par `dev.sh`.
- `logs/dev.log` — sortie standard (stdout) pour le mode background.
- `logs/dev.err.log` — erreurs (stderr) pour le mode background.
- `.run/redriva.pid` — PID du processus lancé en background.

## Usage du script

Se placer dans le répertoire du projet :

```bash
cd /home/kesurof/Projets_Github/Redriva
```

Afficher l'aide :

```bash
./dev.sh -h
```

Démarrer en premier plan (foreground) — utile pour le debug :

```bash
./dev.sh start-foreground
```

Démarrer en arrière-plan (background) — utile pour laisser tourner le service :

```bash
./dev.sh start
# ou
./dev.sh start-bg
```

Recréer le virtualenv puis démarrer en arrière-plan :

```bash
./dev.sh -r start
# ou
./dev.sh --recreate-venv start-bg
```

Arrêter le service background :

```bash
./dev.sh stop
```

Redémarrer :

```bash
./dev.sh restart
```

Afficher l'état (PID) :

```bash
./dev.sh status
```

## Comportement détaillé

- Installation des dépendances : `dev.sh` invoque explicitement le Python du venv pour exécuter `pip install -r requirements.txt`. Aucune commande `pip` globale ni `source activate` d'autres venvs n'est utilisée.
- Isolation runtime : l'application est lancée avec `env -i` (environnement vierge) puis les seules variables explicitement transmises sont : `PATH` (pointant sur `./redriva/bin`), `VIRTUAL_ENV`, `PYTHONNOUSERSITE`, `PYTHONPATH` (pointant sur `./src`) et `HOME`, ainsi que `RD_TOKEN` et `TZ` si définies.
- Logs : en mode background, la sortie standard et d'erreur sont redirigées vers `logs/dev.log` et `logs/dev.err.log` respectivement. Le PID du processus est enregistré dans `.run/redriva.pid`.

## Vérifications et commandes utiles

- Vérifier quel Python est utilisé :

```bash
./redriva/bin/python -c "import sys; print(sys.executable)"
```

- Vérifier qu'un paquet est installé dans le venv (ex: `aiohttp`) :

```bash
./redriva/bin/python -c "import importlib,sys
try:
  m = importlib.import_module('aiohttp')
  print('aiohttp OK', getattr(m,'__version__', '??'))
except Exception as e:
  print('aiohttp missing or import failed:', e)"
```

- Suivre les logs en temps réel (mode background) :

```bash
tail -n 200 -f logs/dev.log logs/dev.err.log
```

- Si vous rencontrez des erreurs d'import au démarrage (ModuleNotFoundError), lancer :

```bash
# recrée venv et force réinstallation des dépendances
./dev.sh -r start-foreground
```

## Recommandations

- Pour le développement interactif et le debug, privilégiez `start-foreground` : vous verrez les logs en temps réel et pourrez interrompre proprement avec Ctrl+C.
- Pour les tests d'intégration ou pour laisser tourner Redriva sur le serveur en dev, utilisez `start` (background) puis `./dev.sh status` et `./dev.sh stop` pour gérer le cycle de vie.
- Évitez d'installer manuellement des paquets avec le pip global du système. Utilisez toujours `./redriva/bin/pip` ou laissez `dev.sh` gérer l'installation.

## Exemple complet - Clean start

```bash
# depuis la racine du projet
./dev.sh -r start  # recrée venv, installe deps et démarre en background
./dev.sh status    # vérifie que le service tourne
tail -f logs/dev.log
```

## Dépannage rapide

- Erreur "ModuleNotFoundError" au lancement : vérifier `logs/dev.err.log` et lancer `./dev.sh -r start-foreground`.
- Le script démarre mais des imports proviennent d'un autre venv : vérifier la sortie de `./redriva/bin/python -c "import sys; print(sys.executable)"` — elle doit pointer sur `.../Redriva/redriva/bin/python`.
- Si le venv est corrompu, supprimer `./redriva/` puis `./dev.sh -r start`.

---

Documentation générée automatiquement par l'outil d'assistance. Si tu veux que j'ajoute un fichier `systemd` d'exemple ou un `docker-compose.override.yml` pour dev, je peux le générer aussi.
