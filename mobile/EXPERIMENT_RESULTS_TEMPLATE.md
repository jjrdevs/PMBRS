# Battery Experiment Results (example filled)

Device: test-device
Device ID: test-device
Network: Wi-Fi
Duration: 30 minutes
Date: 2026-08-08

Summary:

- Baseline daily drain: 1.2%
- Experiment daily drain: 1.4%
- Delta: 0.2%
- Notes on anomalies: none recorded in this quick run

Artifacts location: `mobile/results/experiment_20260808_190420/`

Telemetry summary (from `telemetry_summary.json`):

```
{
	"payload_bytes_sent": 12345,
	"periodic_run_started": 3
}
```

Key findings & mitigations:

- Small observed delta (0.2%) for the 30-minute quick Wi‑Fi run. No immediate mitigation required; recommend monitoring for full-run values.

Acceptance: Pass (quick-run threshold not exceeded)

Owner: mobile eng
