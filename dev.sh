#!/usr/bin/env bash
set -euo pipefail

# Dev script Redriva
# - venv: ./redriva
# - par défaut: démarre au premier plan (foreground)
# - options: start | start-bg | stop | restart | status
# - permet d'arrêter puis relancer pour appliquer des modifications

VENV_DIR="redriva"
PY_BIN=${PY_BIN:-python3}
PID_DIR=".run"
PID_FILE="$PID_DIR/redriva.pid"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/dev.log"
APP="src/web.py"

RECREATE_VENV=0

mkdir -p "$PID_DIR" "$LOG_DIR"

## Parse global flags (support --recreate-venv / -r anywhere, and -h/--help)
PARSED_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --recreate-venv|-r)
      RECREATE_VENV=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./dev.sh [--recreate-venv|-r] <command>

Commands:
  start-foreground   Start the app in foreground (isolated venv)
  start | start-bg   Start the app in background (isolated venv)
  stop               Stop the running background process
  restart            Stop then start in background
  status             Show service status (PID)

Global flags:
  --recreate-venv, -r  Recreate the ./redriva virtualenv before installing deps
  -h, --help            Show this help message

This script ensures full isolation by creating (or reusing) a local virtualenv
at ./redriva and launching the application using the venv's Python. The runtime
is executed with a cleaned environment (env -i) and only essential variables are
passed: RD_TOKEN, TZ, HOME. This avoids accidental usage of other venvs on the host.

Examples:
  ./dev.sh start-foreground          # starts app in isolated venv (foreground)
  ./dev.sh -r start-bg              # recreate venv then start in background
  ./dev.sh --recreate-venv status   # recreate venv (no effect on status) then show status
EOF
      exit 0
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do PARSED_ARGS+=("$1"); shift; done
      ;;
    -* )
      # Unknown option, keep it for later handling or pass-through
      PARSED_ARGS+=("$1")
      shift
      ;;
    *)
      PARSED_ARGS+=("$1")
      shift
      ;;
  esac
done

# Rebuild positional parameters from parsed args (flags removed)
set -- "${PARSED_ARGS[@]:-}"

function ensure_python() {
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    echo "❌ $PY_BIN introuvable. Installez Python puis relancez."
    exit 1
  fi
}

function create_venv() {
  if [ "$RECREATE_VENV" = "1" ] && [ -d "$VENV_DIR" ]; then
    echo "♻️  Recréation du virtualenv $VENV_DIR (option demandée)..."
    rm -rf "$VENV_DIR"
  fi

  if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Création du virtualenv dans ./$VENV_DIR ..."
    "$PY_BIN" -m venv "$VENV_DIR"
  fi
}

function activate_venv() {
  # kept for compatibility but avoided in isolated flows
  # shellcheck disable=SC1090
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  fi
}

function venv_python() {
  if [ -x "$VENV_DIR/bin/python" ]; then
    # Return absolute path to avoid ambiguity with other venvs
    echo "$(pwd)/$VENV_DIR/bin/python"
  else
    echo "$PY_BIN"
  fi
}

function install_deps() {
  # Install strictly into the project venv using its python (no sourcing)
  PYEXEC="$(venv_python)"
  if [ -z "$PYEXEC" ]; then
    echo "❌ Aucun interpréteur Python trouvé pour installer les dépendances"
    exit 1
  fi

  VENV_ABS="$(pwd)/$VENV_DIR"

  if [ -f "requirements.txt" ]; then
    echo "📥 Installation des dépendances dans $VENV_DIR via $PYEXEC (installation isolée)..."
    # Run pip upgrade in a clean environment so external site-packages are not visible
    env -i PATH="$VENV_ABS/bin" VIRTUAL_ENV="$VENV_ABS" PYTHONNOUSERSITE=1 HOME="$HOME" \
      "$PYEXEC" -m pip install --upgrade pip setuptools wheel

    # Install requirements forcing reinstall and ignoring installations detected elsewhere
    env -i PATH="$VENV_ABS/bin" VIRTUAL_ENV="$VENV_ABS" PYTHONNOUSERSITE=1 HOME="$HOME" \
      "$PYEXEC" -m pip install --no-cache-dir --ignore-installed -r requirements.txt
  else
    echo "⚠️ requirements.txt introuvable — passez si inutilisé."
  fi
}

function start_foreground() {
  ensure_python
  create_venv
  install_deps
  echo "🚀 Démarrage en premier plan de $APP dans le venv ./$VENV_DIR (Ctrl+C pour arrêter)..."

  PYEXEC="$(venv_python)"
  VENV_ABS="$(pwd)/$VENV_DIR"

  # Clean potentially inherited Python env vars
  unset PYTHONHOME PYENV_VIRTUALENV PYENV_VERSION

  # Launch in a clean environment: only expose necessary vars
  exec env -i \
    PATH="$VENV_ABS/bin" \
    VIRTUAL_ENV="$VENV_ABS" \
    PYTHONNOUSERSITE=1 \
    PYTHONPATH="$(pwd)/src" \
    RD_TOKEN="${RD_TOKEN:-}" \
    TZ="${TZ:-}" \
    HOME="${HOME:-/root}" \
    "$PYEXEC" "$APP"
}

function start_bg() {
  ensure_python
  create_venv
  install_deps

  echo "🚀 Démarrage en arrière-plan de $APP dans le venv ./$VENV_DIR, logs -> $LOG_FILE"

  PYEXEC="$(venv_python)"
  VENV_ABS="$(pwd)/$VENV_DIR"

  # Start nohup in a fully isolated environment (env -i)
  nohup env -i \
    PATH="$VENV_ABS/bin" \
    VIRTUAL_ENV="$VENV_ABS" \
    PYTHONNOUSERSITE=1 \
    PYTHONPATH="$(pwd)/src" \
    RD_TOKEN="${RD_TOKEN:-}" \
    TZ="${TZ:-}" \
    HOME="${HOME:-/root}" \
    "$PYEXEC" "$APP" >> "$LOG_FILE" 2>> "$LOG_DIR/dev.err.log" &

  PID=$!
  echo "$PID" > "$PID_FILE"
  echo "PID $PID enregistré dans $PID_FILE"

  # small sanity check: ensure the PID exists
  sleep 0.4
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "✅ Process $PID confirmé démarré"
  else
    echo "⚠️ Process $PID non trouvé après démarrage — vérifiez les logs ($LOG_FILE)"
  fi
}

function stop_app() {
  if [ ! -f "$PID_FILE" ]; then
    echo "ℹ️ Aucun PID trouvé ($PID_FILE). Recherche de processus fallback..."
    # fallback : chercher un processus python exécutant src/web.py
    PIDS=$(pgrep -f "src/web.py" || true)
    if [ -z "$PIDS" ]; then
      echo "ℹ️ Aucun processus fallback trouvé.";
      return 0
    fi
    for PID in $PIDS; do
      echo "⏹️ Arrêt du processus fallback $PID ..."
      kill "$PID" || true
      sleep 1
      if kill -0 "$PID" >/dev/null 2>&1; then
        echo "⚠️ Le processus $PID n'a pas fermé, envoi SIGKILL."
        kill -9 "$PID" || true
      fi
    done
    return 0
  fi
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "⏹️ Arrêt du processus $PID ..."
    kill "$PID"
    sleep 1
    if kill -0 "$PID" >/dev/null 2>&1; then
      echo "⚠️ Le processus n'a pas fermé, envoi SIGKILL."
      kill -9 "$PID" || true
    fi
  else
    echo "ℹ️ PID $PID non actif."
  fi
  rm -f "$PID_FILE"
}

function status_app() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" >/dev/null 2>&1; then
      echo "✅ En cours (PID $PID)"
      return 0
    else
      echo "❌ PID $PID absent/éteint."
      return 1
    fi
  else
    echo "ℹ️ Aucun PID enregistré."
    return 1
  fi
}

## If multiple arguments are passed, treat them as a sequence of sub-commands
if [ "$#" -gt 1 ]; then
  for tok in "$@"; do
    case "$tok" in
      start|start-bg|start-foreground|stop|restart|status)
        "$0" "$tok"
        ;;
      *)
        # ignore stray tokens (for example if the user accidentally typed './dev.sh' in the same line)
        echo "⚠️ Ignoring token '$tok' (not a subcommand)"
        ;;
    esac
  done
  exit 0
fi

case "${1:-}" in
  ""|"start-foreground" )
    start_foreground
    ;;
  "start"|"start-bg" )
    start_bg
    ;;
  "stop" )
    stop_app
    ;;
  "restart" )
    stop_app
    start_bg
    ;;
  "status" )
    status_app
    ;;
  * )
    echo "Usage: $0 [start-foreground|start|start-bg|stop|restart|status]"
    exit 2
    ;;
esac
