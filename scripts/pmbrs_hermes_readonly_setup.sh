#!/usr/bin/env bash
set -euo pipefail

PMBRS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTSIDE_BASE="/home/jjrdev/.pmbrs-private"
RAW_ROOT="$OUTSIDE_BASE/store/raw"
SUMMARY_ROOT="$OUTSIDE_BASE/store/summary"
STATE_ROOT="$OUTSIDE_BASE/state"
CHECKPOINT_ROOT="$OUTSIDE_BASE/checkpoints"
QUEUE_ROOT="$OUTSIDE_BASE/store/pending"
HERMES_RO="$OUTSIDE_BASE/hermes-readonly"

mkdir -p "$RAW_ROOT" "$SUMMARY_ROOT" "$STATE_ROOT" "$CHECKPOINT_ROOT" "$QUEUE_ROOT" "$HERMES_RO"
chmod 700 "$OUTSIDE_BASE" "$RAW_ROOT" "$SUMMARY_ROOT" "$STATE_ROOT" "$CHECKPOINT_ROOT" "$QUEUE_ROOT" "$HERMES_RO"

cat > "$STATE_ROOT/pmbrs_runtime.json" <<EOF
{
  "pmbrs_root": "$PMBRS_ROOT",
  "artifact_root": "$OUTSIDE_BASE/store",
  "raw_root": "$RAW_ROOT",
  "summary_root": "$SUMMARY_ROOT",
  "state_root": "$STATE_ROOT",
  "checkpoint_root": "$CHECKPOINT_ROOT",
  "queue_root": "$QUEUE_ROOT",
  "hermes_readonly_root": "$HERMES_RO",
  "schedule_policy": {
    "default_interval_minutes": 60,
    "checkpoint_mode": "write_after_success",
    "require_success_before_next_run": true,
    "allow_hermes_read_only": true,
    "raw_artifact_authority": true
  }
}
EOF

printf '%s\n' "PMBRS external raw datastore initialized at $OUTSIDE_BASE"
printf '%s\n' "Hermes read-only root: $HERMES_RO"
printf '%s\n' "PMBRS root: $PMBRS_ROOT"
