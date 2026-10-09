#!/bin/sh
set -eu

alembic upgrade head
exec uvicorn homelab_pulse.main:app --host 0.0.0.0 --port 8000

