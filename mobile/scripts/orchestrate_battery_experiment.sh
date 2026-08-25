#!/usr/bin/env bash
# Orchestrate a battery experiment using existing helpers.
# Usage: ./orchestrate_battery_experiment.sh <device-id> <minutes> [results-dir]

DEVICE_ID=${1:-}
DURATION_MIN=${2:-30}
DEST=${3:-results/battery_$(date +%Y%m%d_%H%M%S)}

if [ -z "$DEVICE_ID" ]; then
  echo "Usage: $0 <device-id> <minutes> [results-dir]"
  exit 1
fi

mkdir -p "$DEST"
echo "Starting battery experiment: device=$DEVICE_ID duration=${DURATION_MIN}m -> $DEST"

# Run the existing experiment script (which pulls results into cwd)
./mobile/scripts/run_battery_experiment.sh "$DEVICE_ID" "$DURATION_MIN"

# Move any local captures into the result dir
if [ -f logcat_capture.txt ]; then
  mv logcat_capture.txt "$DEST/" || true
fi

# Collect results from device into DEST
./mobile/scripts/collect_battery_results.sh "$DEVICE_ID" "$DEST"

echo "Battery experiment artifacts are in: $DEST"
echo "Next: upload batterystats to Battery Historian or inspect log files in $DEST"

echo "Done"
