#!/bin/sh
cd "$(dirname "$0")" || exit 1
chmod +x fly_brain.sh 2>/dev/null || true
exec /bin/sh ./fly_brain.sh
