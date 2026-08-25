# Battery Experiment Report — Template

Use this template to record battery experiment results for the PMBRS mobile collector.

Experiment metadata
- Owner: ___________________
- Device model: ___________________
- Android version: ___________________
- Build variant: debug / release
- App version / commit: ___________________
- Date: ___________________
- Network: Wi‑Fi / Cellular
- Duration: ______ minutes

Commands run
```bash
# Reset and run experiment
mobile/scripts/orchestrate_battery_experiment.sh <device-id> <minutes>

# Collect artifacts
mobile/scripts/collect_battery_results.sh <device-id> <dest-dir>
```

Artifacts collected
- `batterystats_after_*.txt`
- `logcat_capture.txt`
- `pmbrs_telemetry.xml`
- profiler traces (if present)

Observations
- Baseline battery delta (device idle): ____%
- App experiment battery delta: ____%
- Notable logcat warnings/errors:
  - 

Telemetry snapshot
- `sync_runs`: ____
- `sync_success`: ____
- `sync_network_failure`: ____
- `payload_bytes_sent`: ____ bytes

Analysis
- Summary of battery impact (short):

- Key drivers (e.g., frequent wakeups, large payloads, retries):

Mitigations applied / recommended
- Increase `syncIntervalHours` to ____
- Enforce `UNMETERED` when `trustedNetworkOnly=true`: yes/no
- Batch artifacts per sync: suggested batch size ____
- Reduce payload size: which fields to trim or sample

Decision / Acceptance
- Acceptable impact (≤ ~1% daily on Wi‑Fi): yes / no
- Next steps: rollback / tune config / run extended test

Attachments
- Link to results folder: `results/battery_YYYYMMDD_HHMMSS`
- Battery Historian export link: ___________________
