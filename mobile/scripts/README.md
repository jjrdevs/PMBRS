# Mobile Scripts

This folder contains helper scripts for running battery experiments and local staged-sync validation.

Scripts

- `run_battery_experiment.sh <device-id> <minutes>`
  - Resets batterystats, clears logcat, captures logcat while sleeping for the specified duration, pulls `batterystats_after_*.txt`.

- `collect_battery_results.sh <device-id> [dest-dir]`
  - Pulls batterystats, logcat_capture.txt, profiler traces, and telemetry prefs into a timestamped `results/` folder.

- `orchestrate_battery_experiment.sh <device-id> <minutes>`
  - Wrapper that runs `run_battery_experiment.sh` then `collect_battery_results.sh` and stores artifacts in `results/`.

- `mock_auth_server.py --port <port> --token <token>`
  - Lightweight Python HTTP server that enforces `Authorization: Bearer <token>` for `/api/v1/artifacts/sync`. Useful for emulator manual integration.

- `run_staged_sync_integration.sh [port] [token]`
  - Starts the local mock auth server, POSTs a sample payload, validates a 200 response, and shuts down the server.

Usage notes

- Emulator: use `http://10.0.2.2:<port>/` as the sync endpoint to point to the host machine.
- Device: ensure `adb` is available and the device is authorized.
- Battery Historian: upload `batterystats_after_*.txt` to Battery Historian for visualization.
