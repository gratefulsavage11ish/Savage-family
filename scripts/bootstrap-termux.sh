#!/usr/bin/env sh
# Tiny bootstrap: installs just enough of Savage AI under $SAVAGE_AI_ROOT for `savage doctor`
# to take over. All real setup logic lives in `savage doctor`. Needs no root.
#   export SAVAGE_AI_ROOT=/data/local/savage-ai
#   ./scripts/bootstrap-termux.sh
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
command -v python3 >/dev/null 2>&1 || { echo "python3 missing: pkg install python" >&2; exit 1; }
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$HERE/savage-ai${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m savage.bootstrap "$@"
