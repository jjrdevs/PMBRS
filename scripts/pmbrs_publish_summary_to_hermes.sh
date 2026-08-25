#!/usr/bin/env bash
set -euo pipefail

PMBRS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PMBRS_ROOT${PYTHONPATH:+:$PYTHONPATH}"

python3 -m src.pmbrs_runtime --run-once

READONLY_ROOT="/home/jjrdev/.pmbrs-private/hermes-readonly"
chmod 555 "$READONLY_ROOT"
find "$READONLY_ROOT" -maxdepth 1 -type f -exec chmod 444 {} +
ls -ld "$READONLY_ROOT"
ls -l "$READONLY_ROOT"
