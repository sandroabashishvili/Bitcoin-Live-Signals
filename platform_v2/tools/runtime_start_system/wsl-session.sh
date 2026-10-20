#!/bin/bash
# Keep one WSL session alive and start the normal project service at sign-in.
set -euo pipefail
exec 9>/home/sandro/SmartSignalHub/platform_v2/runtime/research-wsl-session.lock
/usr/bin/flock -n 9 || exit 0
/usr/bin/systemctl --user is-enabled --quiet smartsignalhub-runtime.service
/usr/bin/systemctl --user start smartsignalhub-runtime.service
exec /usr/bin/sleep infinity
