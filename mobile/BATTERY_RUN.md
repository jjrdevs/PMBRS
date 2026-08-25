# Battery Experiment Checklist

Follow these steps to run the PMBRS mobile battery experiment and collect artifacts.

Prerequisites
- Connected Android device or emulator with `adb` available.
- App built and installed (debug build recommended).
- Ensure device has sufficient battery and stable network for the duration.

Quick run (30m)
1. Install debug build on device: `adb -s <device-id> install -r app/build/outputs/apk/debug/app-debug.apk`
2. Start baseline collection (on device):
   - Clear previous battery stats: `adb -s <device-id> shell dumpsys batterystats --reset`
3. Start the orchestrator (on host):
   ```bash
   cd mobile
   ./scripts/generate_battery_report.sh <device-id> 30
   ```
4. After completion, collect artifacts are saved to `mobile/results/<timestamp>/`.

Full run (24h)
- Replace `30` with `1440` minutes in the command above.

Collecting artifacts manually
- Pull batterystats: `adb -s <device-id> shell dumpsys batterystats > batterystats_after.txt`
- Pull logcat: `adb -s <device-id> logcat -d > logcat_capture.txt`
- Pull app telemetry (debug build):
  `adb -s <device-id> shell "run-as com.pmbrs.mobile cat /data/data/com.pmbrs.mobile/shared_prefs/pmbrs_telemetry.xml" > pmbrs_telemetry.xml`

Uploading to Battery Historian
- Use `batterystats_after.txt` in Battery Historian UI to generate a timeline and histogram.

Analysis guidance
- Compare device baseline vs experiment delta. If Wi‑Fi daily delta >1%, consider mitigation: increase `syncIntervalHours`, enforce `UNMETERED`, batch payloads, or reduce frequency.
