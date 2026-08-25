# PMBRS Mobile Collector

This directory contains the PMBRS mobile collection implementation, including the Android app, integration scripts, and review materials.

## Key artifacts

- `scripts/` — helper scripts for experiment result packaging, privacy signoff, TLS validation, and local tooling.
- `HANDOFF.md` — delivery and reviewer guidance.
- `mobile-privacy-signoff.md` — mobile privacy decision record.
- `results/` — experiment result artifacts.

## Review checklist

1. Apply experiment results with `./scripts/apply_experiment_results.sh results/<timestamp>`.
2. Prepare privacy review artifacts with `./scripts/prepare_privacy_email.sh`.
3. Validate TLS integration using `./scripts/run_staged_tls_integration.sh`.

## Local tooling

- Use `scripts/mock_auth_server_tls.py` to run a local TLS auth mock server.
- Use `scripts/run_staged_tls_integration.sh` for staged TLS endpoint testing.
