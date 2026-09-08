#!/bin/bash
set -euo pipefail
PYTHON="${PYTHON:-python3}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PYTHON" "$HERE/security_query.py"
