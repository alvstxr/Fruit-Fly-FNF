#!/bin/sh
DIR=$(cd "$(dirname "$0")" && pwd)
chmod +x "$DIR/python/fly_brain.sh" "$DIR/python/fly_brain.command" "$DIR/python/fly_brain_stop.sh" 2>/dev/null || true
exec /bin/sh "$DIR/python/fly_brain.sh"
