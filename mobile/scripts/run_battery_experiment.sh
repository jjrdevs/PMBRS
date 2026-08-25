#!/usr/bin/env bash
# Simple helper to run battery experiment steps.
# Usage: ./run_battery_experiment.sh <device-id> <duration-minutes>

DEVICE_ID=${1:-}
DURATION_MIN=${2:-10}

if [ -z "$DEVICE_ID" ]; then
  echo "Usage: $0 <device-id> <duration-minutes>"
  exit 1
fi

echo "Resetting batterystats on $DEVICE_ID"
adb -s "$DEVICE_ID" shell dumpsys batterystats --reset

echo "Clearing logcat"
adb -s "$DEVICE_ID" logcat --clear

echo "Starting logcat capture in background (logcat_capture.txt)"
adb -s "$DEVICE_ID" logcat > logcat_capture.txt &
LOGCAT_PID=$!

echo "Sleeping for $DURATION_MIN minutes..."
sleep $(($DURATION_MIN * 60))

echo "Stopping logcat capture"
kill $LOGCAT_PID || true

OUT_BATT=batterystats_after_$(date +%s).txt
adb -s "$DEVICE_ID" shell dumpsys batterystats > /data/local/tmp/$OUT_BATT
adb -s "$DEVICE_ID" pull /data/local/tmp/$OUT_BATT . || adb -s "$DEVICE_ID" pull $OUT_BATT .

echo "Pulled $OUT_BATT and logcat_capture.txt"

echo "Done"
