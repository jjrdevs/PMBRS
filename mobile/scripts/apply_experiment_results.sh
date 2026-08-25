#!/usr/bin/env bash
# Apply battery experiment results into mobile/HANDOFF.md and the implementation plan
# Usage: ./scripts/apply_experiment_results.sh <results-dir>

set -euo pipefail

RESULTS_DIR=${1:-}
if [ -z "$RESULTS_DIR" ]; then
  echo "Usage: $0 <results-dir>"
  exit 2
fi

if [ ! -d "$RESULTS_DIR" ]; then
  echo "Results directory not found: $RESULTS_DIR"
  exit 3
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_ROOT="$SCRIPT_DIR/.."
HANDOFF="$MOBILE_ROOT/HANDOFF.md"
PLAN="$MOBILE_ROOT/../docs/ingestion/adapters/mobile-collection-implementation-plan-next-steps.md"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST_DIR="$MOBILE_ROOT/results/experiment_${TIMESTAMP}"
mkdir -p "$DEST_DIR"

# Copy files
cp -r "$RESULTS_DIR"/* "$DEST_DIR/" || true

echo "Applying experiment results from $RESULTS_DIR to $HANDOFF"

if [ -f "$DEST_DIR/battery_report.md" ]; then
  echo "- Experiment report: results/experiment_${TIMESTAMP}/battery_report.md" >> "$HANDOFF"
fi

if [ -f "$DEST_DIR/telemetry_summary.json" ]; then
  echo "- Telemetry summary: results/experiment_${TIMESTAMP}/telemetry_summary.json" >> "$HANDOFF"
fi

echo "Updating implementation plan with brief entry"
if [ -w "$PLAN" ]; then
  printf "\n- Experiment run: results/experiment_%s (automatically recorded)\n" "$TIMESTAMP" >> "$PLAN"
fi

echo "Results applied to $HANDOFF and copied to $DEST_DIR"
