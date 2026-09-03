#!/usr/bin/env sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CAMPAIGN=${1:-standard}
shift 2>/dev/null || true
exec python3 "$HERE/levelupdiag.py" run "$CAMPAIGN" "$@"
