# Mobile Observability & Battery Experiment Runbook

Purpose
- Provide repeatable steps to measure background battery impact and observe WorkManager/periodic sync behavior.

Quick steps
1. Connect the test device or emulator and ensure `adb` is available.

2. Reset battery stats:
```bash
adb devices
adb -s <device-id> shell dumpsys batterystats --reset
```

3. Clear logcat and start capturing:
```bash
adb -s <device-id> logcat --clear
adb -s <device-id> logcat > logcat_capture.txt &
```

4. Run the scenario
- Install and run the app; ensure periodic sync is enabled and `trustedNetworkOnly` is set as desired.
- Let the device run idle for the planned duration (10–30 minutes for quick checks, 24h for full-day runs).

5. Capture stats after run:
```bash
adb -s <device-id> shell dumpsys batterystats > batterystats_after.txt
adb -s <device-id> pull batterystats_after.txt
adb -s <device-id> pull logcat_capture.txt
```

6. Optional: use Battery Historian
- Upload `batterystats_after.txt` to Battery Historian to visualize power usage over time.

Observability checklist
- Confirm `PMBRSSyncWorker` run timestamps in `logcat` and correlate with `lastSyncLog` entries in the app.
- Verify network activity and payload sizes via Android Studio Network profiler or `adb shell dumpsys netstats`.
- Confirm `WorkManager` run info using an in-app debug endpoint or logs.

Recording and reporting
- Store `batterystats_after.txt`, `logcat_capture.txt`, and profiler traces in the delivery review folder.
- Note device model, Android version, idle duration, sync interval, and `trustedNetworkOnly` setting.

Script helper
- See `mobile/scripts/run_battery_experiment.sh` for a convenience wrapper to run the basic steps.

Result collection helper
- After a run, use `mobile/scripts/collect_battery_results.sh` to pull all known artifacts into a timestamped results folder on your workstation:
```bash
# Example: collect results from device 'emulator-5554'
./mobile/scripts/collect_battery_results.sh emulator-5554
```


Telemetry & quick validation
- Inspect the locally persisted telemetry counters (useful for payload size and sync run counts):
```bash
# Dump telemetry SharedPreferences from a connected device (package must match your debug package id)
adb shell "run-as com.pmbrs.mobile cat /data/data/com.pmbrs.mobile/shared_prefs/pmbrs_telemetry.xml"
```

- Refresh and clear telemetry from the app: open the app's debug view (`MobileHomeScreen`) and use `Refresh telemetry` / `Clear telemetry` buttons.

- Check WorkManager runs in the logcat (filter by `PMBRSSyncWorker` or `WorkManager` tags):
```bash
adb -s <device-id> logcat -s PMBRSSyncWorker WorkManager
```

- Correlate `lastSyncLog` in-app with the `logcat` timestamps to validate behavior.

Network & payload inspection
- Use Android Studio Network Profiler during a manual sync to measure exact bytes sent, or approximate size via telemetry `payload_bytes_sent` counter.
- For a quick adb check of network stats:
```bash
adb shell dumpsys netstats | grep -A 5 pmbrs
```

Notes on repeatability
- Run at least two quick runs (10–30m) on Wi‑Fi and cellular to verify baseline. If results vary, increase sample duration and device set.
- When collecting for a 24h run, ensure the device is on a stable power source and set `trustedNetworkOnly` as needed to emulate real-world constraints.
