#!/bin/bash
# Windows sign-in task target. No legacy launcher and no second runtime copy.
set -euo pipefail
exec 9>/home/sandro/SmartSignalHub/platform_v2/runtime/research-wsl-session.lock
/usr/bin/flock -n 9 || exit 0
test -f /home/sandro/SmartSignalHub/platform_v2/deployment/deploy/activation.json
/usr/bin/systemctl --user is-enabled --quiet smartsignalhub-runtime.service
/usr/bin/systemctl --user start smartsignalhub-runtime.service
# WSL may exit when no foreground Linux sessions remain; retain this session.
exec /usr/bin/sleep infinity
