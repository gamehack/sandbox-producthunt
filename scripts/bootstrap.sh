#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "$0")/.."
root="$(pwd -P)"
[[ "$root" == /data/opt/sandbox-producthunt ]] || { echo "Deploy to /data/opt/sandbox-producthunt" >&2; exit 2; }
python="${PYTHON_BIN:-python3}"
"$python" -c 'import sys; assert sys.version_info >= (3,11), "Python >=3.11 required"'
command -v git >/dev/null
"$python" -m venv .venv
.venv/bin/python -m pip install .
mkdir -p data output logs
if [[ ! -e .env ]]; then install -m 600 .env.example .env; fi
chmod 600 .env
echo "Installed. Configure .env privately; run scripts/run.sh doctor."
