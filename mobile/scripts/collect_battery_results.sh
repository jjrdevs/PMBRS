#!/usr/bin/env bash
# Collect pulled battery experiment artifacts into a timestamped results folder.
# Usage: ./collect_battery_results.sh <device-id> [dest-dir]

DEVICE_ID=${1:-}
DEST=${2:-results/battery_$(date +%Y%m%d_%H%M%S)}

if [ -z "$DEVICE_ID" ]; then
  echo "Usage: $0 <device-id> [dest-dir]"
  exit 1
fi

mkdir -p "$DEST"

echo "Looking for batterystats files on device..."
# Look for known batterystats files in /data/local/tmp
TMP_LIST=$(adb -s "$DEVICE_ID" shell ls /data/local/tmp 2>/dev/null | tr -d '\r' | grep -E '^batterystats_after' || true)

if [ -n "$TMP_LIST" ]; then
  for f in $TMP_LIST; do
    echo "Pulling /data/local/tmp/$f -> $DEST/"
    adb -s "$DEVICE_ID" pull "/data/local/tmp/$f" "$DEST/" || true
  done
else
  # Fallback to common filename
  echo "Pulling batterystats_after.txt (fallback)"
  adb -s "$DEVICE_ID" pull "/data/local/tmp/batterystats_after.txt" "$DEST/" 2>/dev/null || adb -s "$DEVICE_ID" pull "batterystats_after.txt" "$DEST/" || true
fi

# Pull logcat capture if present
if adb -s "$DEVICE_ID" shell "ls logcat_capture.txt" >/dev/null 2>&1; then
  echo "Pulling logcat_capture.txt -> $DEST/"
  adb -s "$DEVICE_ID" pull "logcat_capture.txt" "$DEST/" || true
else
  # Try /data/local/tmp
  if adb -s "$DEVICE_ID" shell "ls /data/local/tmp/logcat_capture.txt" >/dev/null 2>&1; then
    echo "Pulling /data/local/tmp/logcat_capture.txt -> $DEST/"
    adb -s "$DEVICE_ID" pull "/data/local/tmp/logcat_capture.txt" "$DEST/" || true
  fi
fi

# Optional: pull profiler traces if a known path is used
# Example: /sdcard/pmbrs_profiler_trace.trace
if adb -s "$DEVICE_ID" shell "ls /sdcard/pmbrs_profiler_trace.trace" >/dev/null 2>&1; then
  echo "Pulling profiler trace -> $DEST/"
  adb -s "$DEVICE_ID" pull "/sdcard/pmbrs_profiler_trace.trace" "$DEST/" || true
fi

# Dump telemetry prefs (requires debug app and correct package)
echo "Attempting to dump telemetry prefs"
adb -s "$DEVICE_ID" shell "run-as com.pmbrs.mobile cat /data/data/com.pmbrs.mobile/shared_prefs/pmbrs_telemetry.xml" > "$DEST/pmbrs_telemetry.xml" 2>/dev/null || true

echo "Results collected in $DEST"

echo "Done"
