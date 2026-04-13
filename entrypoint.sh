#!/usr/bin/env sh
# Runtime entrypoint: apply PUID/PGID so /config files end up owned
# by the right user on the Unraid host (defaults: 99:100 = nobody:users).
set -e

PUID="${PUID:-99}"
PGID="${PGID:-100}"

# If the caller already runs as the target uid/gid, skip the chown dance.
CURRENT_UID=$(id -u)
if [ "$CURRENT_UID" = "0" ]; then
    # Running as root (e.g. the user overrode USER in docker run).
    # Adjust the aicomic uid/gid to match what Unraid expects.
    groupmod -o -g "${PGID}" users 2>/dev/null || true
    usermod  -o -u "${PUID}" aicomic 2>/dev/null || true
    # Fix /config ownership in case it was mounted as a different uid.
    chown -R aicomic:users /config 2>/dev/null || true
    exec gosu aicomic:users "$@"
else
    # Already a non-root user (the normal path in the container) — just run.
    exec "$@"
fi
