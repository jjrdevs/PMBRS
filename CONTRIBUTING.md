# Contributing

## Local test commands

```sh
# Python
python -m pip install -r requirements.txt pytest
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install duckdb pandas altair scikit-learn
python -m pytest tests/ -v

# Android
cd mobile && ./gradlew :app:testDebugUnitTest
```

## CI status

CI (`workflows/ci-integration.yml` — see its header note about the
`.github/workflows/` relocation) runs on every push/PR to `main` with two
jobs: **Python tests** and **Android**.

- **Green ✓** — both jobs passed on the CI runner.
- **Red ✗** — open the run in the Actions tab: the failing step and the
  first failing test / Gradle task are in the log. `mobile-battery-results`
  and `pytest-failure-log` artifacts are attached when a run fails.
- **Cancelled ⊗** — a prior run superseded by a re-push (workflow
  `concurrency` cancels stale runs).
