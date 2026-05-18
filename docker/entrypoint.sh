#!/usr/bin/env bash
# ─── Container entrypoint ───────────────────────────────────────────
# Usage:
#   docker run … api        (default — start FastAPI + scheduler)
#   docker run … worker     (scheduler-only, no HTTP server)
#   docker run … migrate    (run Alembic migrations against $DATABASE_URL)
#   docker run … shell      (drop into bash)
# ────────────────────────────────────────────────────────────────────
set -euo pipefail

cmd="${1:-api}"

case "$cmd" in
  api)
    exec uvicorn api.main:app \
      --host "${API_HOST:-0.0.0.0}" \
      --port "${API_PORT:-8000}" \
      --workers "${API_WORKERS:-2}" \
      --no-access-log \
      --proxy-headers \
      --forwarded-allow-ips='*'
    ;;
  worker)
    # Same app, but disable the HTTP server (run a tiny script that just blocks on the scheduler)
    export SCHEDULER_ENABLED=true
    exec python -c "
import asyncio, signal
from api.main import lifespan, create_app

async def main():
    app = create_app()
    async with lifespan(app):
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for s in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(s, stop.set)
        await stop.wait()

asyncio.run(main())
"
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    echo "unknown command: $cmd"
    echo "available: api | worker | migrate | shell"
    exit 1
    ;;
esac
