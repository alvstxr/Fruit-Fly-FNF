#!/bin/sh
DIR=$(cd "$(dirname "$0")" && pwd)
exec /bin/sh "$DIR/python/fly_brain_stop.sh"
