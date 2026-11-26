#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "$0")/.."
root="$(pwd -P)"
[[ "$root" == /data/opt/sandbox-producthunt ]] || { echo "Unexpected deployment directory" >&2; exit 2; }
export HOME=/data/home
export DSH_HOME="${DSH_HOME:-/data/home/.dsh}"
export PATH="/data/opt/npm/bin:/data/opt/bin:$PATH"
if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  set +u
  source "$HOME/.nvm/nvm.sh"
  nvm use --silent 24 >/dev/null
  set -u
fi
exec "$root/.venv/bin/sandbox-producthunt" --root "$root" "$@"
