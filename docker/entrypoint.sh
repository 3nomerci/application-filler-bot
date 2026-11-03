#!/bin/sh
set -eu
umask 077
mkdir -p "$HOME"
desktop=true
case " $* " in
  *" --headless "*|*" init "*|*" validate "*) desktop=false ;;
esac
if [ "$desktop" = false ]; then
  exec /app/.venv/bin/application-filler "$@"
fi
vnc_password=$(/app/.venv/bin/python -c 'import secrets; print(secrets.token_hex(4))')
x11vnc -storepasswd "$vnc_password" /tmp/vnc.pass >/dev/null 2>&1
Xvfb :99 -screen 0 1440x1000x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
xvfb_pid=$!
cleanup() {
  kill "$xvfb_pid" "${wm_pid:-}" "${vnc_pid:-}" "${web_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
attempt=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
  attempt=$((attempt+1))
  [ "$attempt" -lt 50 ] || { echo 'Virtual display failed to start.' >&2; exit 1; }
  sleep 0.1
done
openbox >/tmp/openbox.log 2>&1 &
wm_pid=$!
x11vnc -display :99 -rfbauth /tmp/vnc.pass -forever -shared -localhost \
  -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
vnc_pid=$!
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
web_pid=$!
echo "Browser: http://localhost:6080/vnc.html — temporary viewing password: $vnc_password"
unset vnc_password
/app/.venv/bin/application-filler "$@"
