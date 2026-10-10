#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    key=${line%%=*}
    value=${line#*=}
    eval "existing=\${$key-}"
    if [ -z "$existing" ]; then
      export "$key=$value"
    fi
  done < .env
fi
py="${PYTHON:-python3}"
exec "$py" run.py "$@"
