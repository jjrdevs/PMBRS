#!/usr/bin/env bash
# Automate battery experiment run and generate a filled report
# Usage: ./scripts/generate_battery_report.sh <device-id> <minutes> [dest-dir]

DEVICE_ID=${1:-}
DURATION=${2:-30}
DEST=${3:-results/battery_$(date +%Y%m%d_%H%M%S)}

if [ -z "$DEVICE_ID" ]; then
  echo "Usage: $0 <device-id> <minutes> [dest-dir]"
  exit 1
fi

mkdir -p "$DEST"
echo "Running battery experiment: device=$DEVICE_ID duration=${DURATION}m -> $DEST"

# Run orchestrator
./scripts/orchestrate_battery_experiment.sh "$DEVICE_ID" "$DURATION"

# Move any captures into DEST
if [ -f logcat_capture.txt ]; then
  mv logcat_capture.txt "$DEST/" || true
fi

# Collect battery artifacts (this will pull batterystats into DEST)
./scripts/collect_battery_results.sh "$DEVICE_ID" "$DEST"

# Parse telemetry if present
if [ -f "$DEST/pmbrs_telemetry.xml" ]; then
  echo "Parsing telemetry..."
  python3 ./scripts/parse_telemetry.py "$DEST/pmbrs_telemetry.xml" > "$DEST/telemetry_summary.json" || true
fi

# Fill report template
TEMPLATE=../docs/experiments/battery_experiment_report_template.md
OUTREPORT="$DEST/battery_report.md"

if [ -f "$TEMPLATE" ]; then
  cp "$TEMPLATE" "$OUTREPORT"
  sed -i "s/Owner: ___________________/Owner: automated-run/" "$OUTREPORT"
  sed -i "s/Date: ___________________/Date: $(date +%Y-%m-%d)/" "$OUTREPORT"
  sed -i "s/Duration: ______ minutes/Duration: ${DURATION} minutes/" "$OUTREPORT"
  if [ -f "$DEST/telemetry_summary.json" ]; then
    PAYLOAD_BYTES=$(python3 -c "import json,sys;print(json.load(open('$DEST/telemetry_summary.json')).get('payload_bytes_sent', ''))")
    sed -i "s/payload_bytes_sent: ____ bytes/payload_bytes_sent: ${PAYLOAD_BYTES} bytes/" "$OUTREPORT" || true
  fi
  echo "Report generated: $OUTREPORT"
else
  echo "Template not found at $TEMPLATE; skipping report generation"
fi

echo "Done"
