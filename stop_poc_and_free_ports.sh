#!/usr/bin/env bash
# Stop all NVFlare POC processes and free ports 8002, 8003.
# Run this before a fresh "start POC" when you see "address already in use" or clients "target_unreachable".

set -u
echo "Stopping NVFlare POC and freeing ports 8002, 8003..."

# 1) Try graceful stop (may fail if server is dead; ignore)
if command -v nvflare &>/dev/null; then
  NVFLARE_POC_SSL_VERIFY=0 nvflare poc stop &>/dev/null || true
fi
sleep 2

# 2) Kill processes bound to 8002 / 8003 (Linux).
# Prefer ss/lsof to identify PIDs, and kill process groups to prevent respawn.
kill_pid_tree() {
  local pid="$1"
  [[ -z "${pid:-}" ]] && return 0
  if kill -0 "$pid" 2>/dev/null; then
    local pgid
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ -n "$pgid" ]]; then
      kill -TERM "-$pgid" 2>/dev/null || true
      sleep 1
      kill -KILL "-$pgid" 2>/dev/null || true
    fi
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

port_pids=""
if command -v ss &>/dev/null; then
  port_pids="$(ss -ltnp 2>/dev/null | awk '/:(8002|8003)\\b/ {print $NF}' | sed -n 's/.*pid=\\([0-9]\\+\\).*/\\1/p' | sort -u | tr '\\n' ' ' || true)"
fi
if [[ -z "$port_pids" ]] && command -v lsof &>/dev/null; then
  port_pids="$(lsof -ti :8002 -sTCP:LISTEN 2>/dev/null || true) $(lsof -ti :8003 -sTCP:LISTEN 2>/dev/null || true)"
fi
for pid in $port_pids; do
  kill_pid_tree "$pid"
done

# Fallback: fuser kill (may require sudo if ports owned by another user)
if command -v fuser &>/dev/null; then
  fuser -k 8002/tcp 8003/tcp 2>/dev/null || true
fi
sleep 2

# 3) Kill any remaining nvflare poc / fed server / fed client processes
pkill -TERM -f "nvflare\\.cli poc" 2>/dev/null || true
pkill -TERM -f "nvflare\\.private\\.fed\\.server\\.fed_server" 2>/dev/null || true
pkill -TERM -f "nvflare\\.private\\.fed\\.client" 2>/dev/null || true
pkill -TERM -f "nvflare\\.private\\.fed\\.app\\.client\\.client_train" 2>/dev/null || true
pkill -TERM -f "nvflare\\.private\\.fed\\.app\\.server\\.server_train" 2>/dev/null || true
sleep 2
pkill -KILL -f "nvflare\\.cli poc" 2>/dev/null || true
pkill -KILL -f "nvflare\\.private\\.fed\\.server\\.fed_server" 2>/dev/null || true
pkill -KILL -f "nvflare\\.private\\.fed\\.client" 2>/dev/null || true
pkill -KILL -f "nvflare\\.private\\.fed\\.app\\.client\\.client_train" 2>/dev/null || true
pkill -KILL -f "nvflare\\.private\\.fed\\.app\\.server\\.server_train" 2>/dev/null || true
sleep 2

# 4) Double-check ports are free
if command -v ss &>/dev/null; then
  if ss -ltnp 2>/dev/null | grep -qE ':(8002|8003)\b'; then
    echo "WARNING: Ports 8002 or 8003 still in use."
    echo "Try: sudo fuser -k 8002/tcp 8003/tcp"
    echo "Then: ss -ltnp | egrep ':(8002|8003)\\b'"
  else
    echo "Ports 8002 and 8003 are free."
  fi
fi
echo "Done. You can start POC with: ./start_nvflare.sh"
