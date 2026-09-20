#!/bin/sh
export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"

DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR" || exit 1

if [ "$1" = "--detach" ]; then
	shift
	if command -v nohup >/dev/null 2>&1; then
		nohup "$0" "$@" >/tmp/fly_fnf_brain.log 2>&1 &
	else
		"$0" "$@" >/tmp/fly_fnf_brain.log 2>&1 &
	fi
	exit 0
fi

have_cv() {
	"$1" -c "import cv2, numpy" >/dev/null 2>&1
}

try_install() {
	"$1" -m pip install --user numpy opencv-python >/dev/null 2>&1 || true
	"$1" -m pip3 install --user numpy opencv-python >/dev/null 2>&1 || true
}

run_one() {
	if command -v "$1" >/dev/null 2>&1; then
		have_cv "$1" || try_install "$1"
		if have_cv "$1"; then
			exec "$1" fly_bridge.py
		fi
	fi
}

run_one python3
run_one python

echo "Install Python 3, then:"
echo "  python3 -m pip install numpy opencv-python"
echo "Then run this script again."
exit 1
