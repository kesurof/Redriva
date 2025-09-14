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

mkdir -p "$PID_DIR" "$LOG_DIR"

function ensure_python() {
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    echo "❌ $PY_BIN introuvable. Installez Python puis relancez."
    exit 1
  fi
}

function create_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Création du virtualenv dans ./$VENV_DIR ..."
    "$PY_BIN" -m venv "$VENV_DIR"
  fi
}

function activate_venv() {
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
}

function install_deps() {
  activate_venv
  if [ -f "requirements.txt" ]; then
    echo "📥 Installation des dépendances depuis requirements.txt..."
    python -m pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
  else
    echo "⚠️ requirements.txt introuvable — passez si inutilisé."
  fi
}

function start_foreground() {
  ensure_python
  create_venv
  install_deps
  echo "🚀 Démarrage en premier plan de $APP (Ctrl+C pour arrêter)..."
  activate_venv
  exec python "$APP"
}

function start_bg() {
  ensure_python
  create_venv
  install_deps
  activate_venv
  echo "🚀 Démarrage en arrière-plan, logs -> $LOG_FILE"
  nohup python "$APP" >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "PID $(cat $PID_FILE) enregistré dans $PID_FILE"
}

function stop_app() {
  if [ ! -f "$PID_FILE" ]; then
    echo "ℹ️ Aucun PID trouvé ($PID_FILE)."
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
