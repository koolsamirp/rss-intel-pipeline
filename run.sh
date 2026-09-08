#!/bin/bash
# One command: run the pipeline, then print the security report.
set -euo pipefail

# Use $PYTHON if set, else the active python3 on PATH.
PYTHON="${PYTHON:-python3}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Running RSS Intelligence Pipeline..."
"$PYTHON" "$HERE/main.py" "$@"

echo ""
echo "🔒 Security Intelligence Report:"
"$PYTHON" "$HERE/security_query.py"
