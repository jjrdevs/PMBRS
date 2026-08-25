## PR checklist — Mobile collector

Before requesting review, please ensure the following:

- [ ] Unit tests pass (`./gradlew :app:testDebugUnitTest`).
- [ ] If this PR affects background behaviour, run a quick battery experiment and attach `mobile/results/<timestamp>/battery_report.md`.
- [ ] If this PR affects persisted fields, retention, or telemetry, attach a privacy sign-off or request review from the privacy team.
- [ ] For staged-sync or TLS/auth changes, run `./mobile/scripts/run_staged_sync_integration.sh` locally and add the output to the PR.

Add reviewer notes and links to artifacts (CI artifact link, battery report, privacy signoff):

```
CI artifacts: <link>
battery report: mobile/results/<timestamp>/battery_report.md
privacy signoff: docs/privacy/mobile-privacy-signoff.md
```
