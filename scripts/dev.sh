#!/usr/bin/env bash
# Start / stop everything Genesis RAG needs for local development.
#   scripts/dev.sh start   -> Redis, backend (:8000), frontend (:3000)
#   scripts/dev.sh stop
#   scripts/dev.sh status
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run"; mkdir -p "$RUN"
PY="${PYTHON:-python3}"; [ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"

start_bg() { # name, logfile, command string
  local name=$1 log=$2 cmd=$3
  if [ -f "$RUN/$name.pid" ] && kill -0 "$(cat "$RUN/$name.pid")" 2>/dev/null; then echo "$name already running"; return; fi
  # the shell writes its own pid then execs the command, so the pid file holds the real process
  (cd "$ROOT" && setsid nohup bash -c "echo \$\$ >'$RUN/$name.pid'; exec $cmd" >"$log" 2>&1 &)
  echo "started $name (log: $log)"
}

case "${1:-start}" in
  start)
    if ! redis-cli ping >/dev/null 2>&1; then
      if command -v redis-stack-server >/dev/null; then start_bg redis "$RUN/redis.log" "redis-stack-server"
      else start_bg redis "$RUN/redis.log" "redis-server"; fi
      sleep 1
    fi
    start_bg backend "$RUN/backend.log" "\"$PY\" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    [ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)
    start_bg frontend "$RUN/frontend.log" "bash -c \"cd '$ROOT/frontend' && exec npm run dev -- -p 3000\""
    echo "Genesis RAG: frontend http://localhost:3000  backend http://localhost:8000/docs"
    ;;
  stop)
    for n in frontend backend redis; do
      if [ -f "$RUN/$n.pid" ]; then
        pid=$(cat "$RUN/$n.pid")
        kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
      fi
      rm -f "$RUN/$n.pid"
    done
    echo stopped
    ;;
  status)
    curl -s -m 3 localhost:8000/health/ || echo "backend down"; echo
    curl -s -m 3 -o /dev/null -w "frontend %{http_code}\n" localhost:3000 || echo "frontend down"
    ;;
esac
