"""Integration tests for the Step 3 compaction flags wired into the nightly.

Exercises the REAL `main()` (subprocess) against the REAL inbox (read-only)
but isolates all outputs (raw_root/manifest/workdir) to a tmp dir and caps
work with `--max-windows` so the tests stay fast and never touch the real
store. Covers:

1. `--no-compact`         → exit 0, JSON summary has NO `compaction` key.
2. compact success        → exit 0, JSON `compaction.windows_loaded >= 1`.
3. compact failure (bogus span) → exit 5, JSON `status=error, stage=compaction`.

Skips cleanly if the real inbox (or any files in it) is absent — these are
integration tests that depend on a real export on disk.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT
REAL_INBOX = Path(os.path.expanduser("~/.pmbrs-private/store/inbox/wearable"))
SCRIPT = ROOT / "scripts" / "pmbrs_wearable_nightly.py"

# Skip cleanly if the real inbox is gone or empty (these need a real source).
_inbox_files = None
if REAL_INBOX.is_dir():
    _inbox_files = [
        p for p in REAL_INBOX.rglob("*")
        if p.is_file() and p.name.lower().endswith((".csv", ".json"))
    ]
if not _inbox_files:
    pytest.skip(
        f"real inbox {REAL_INBOX} has no export files; "
        "these integration tests need them on disk.",
        allow_module_level=True,
    )


def _run_nightly(workdir: Path, *extra: str) -> tuple[int, str, str]:
    """Run the nightly script as a subprocess with --json, return (rc, stdout, stderr)."""
    outstore = workdir / "store"
    man = workdir / "man.json"
    wd = workdir / "work"
    for d in (outstore, wd):
        d.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(SCRIPT),
        "--transport", "inbox",
        "--inbox-root", str(REAL_INBOX),
        "--raw-root", str(outstore),
        "--manifest", str(man),
        "--workdir", str(wd),
        "--max-windows", "60",   # cap work; these tests exercise flags, not full volume
        "--json",
    ] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def _json_block(stdout: str) -> dict:
    """Parse the JSON summary out of stdout.

    ``--json`` still emits a leading plain-text transport line (e.g.
    ``transport=inbox (859 file(s) pending at ...)``) before the pretty-printed
    JSON object, so we locate the first ``{`` and parse from there to the end.
    """
    idx = stdout.find("{")
    assert idx >= 0, f"no JSON object in stdout: {stdout!r}"
    return json.loads(stdout[idx:])


# ── 1. --no-compact: no compaction block ──────────────────────────────────────

def test_no_compact_flag_suppresses_compaction(tmp_path):
    rc, out, err = _run_nightly(tmp_path, "--no-compact")
    assert rc == 0, f"exit {rc}\nstdout={out}\nstderr={err}"
    # The JSON summary must be parseable and free of a compaction block.
    summary = _json_block(out)
    assert "compaction" not in summary, (
        "--no-compact should NOT include a compaction block in the summary; got:"
        f" {summary.get('compaction')}"
    )
    # Producer stats are still present.
    assert summary.get("windows_emitted", 0) >= 1, summary


# ── 2. compact success: compaction block with >=1 window ──────────────────────

def test_compact_success_flag_emits_compaction_block(tmp_path):
    rc, out, err = _run_nightly(tmp_path)
    if rc == 5:
        pytest.fail(f"compact path unexpectedly failed: stdout={out}\nstderr={err}")
    assert rc == 0, f"exit {rc}\nstdout={out}\nstderr={err}"
    summary = _json_block(out)
    comp = summary.get("compaction")
    assert comp is not None, (
        "compact path should include a 'compaction' block; summary keys:"
        f" {sorted(summary.keys())}"
    )
    assert comp["ok"] is True, comp
    assert comp["windows_loaded"] >= 1, comp
    assert comp["parquet"]["ok"] is True, comp  # pyarrow is installed (confirmed)


# ── 3. compact failure (bogus span) → exit 5 ──────────────────────────────────

def test_compact_failure_bogus_span_returns_exit_5(tmp_path):
    rc, out, err = _run_nightly(tmp_path, "--compact-spans", "bogus")
    # The error line goes to stderr; the JSON error block goes to stdout when
    # --json is set (which _run_nightly passes).
    assert rc == 5, (
        f"expected exit code 5 when compaction raises, got {rc}\n"
        f"stdout={out}\nstderr={err}"
    )
    # stderr should carry the error message.
    assert "compaction" in (err or "").lower(), f"stderr lacks compaction error: {err!r}"
    # stdout carries the single-line JSON error block (the --json path).
    err_block = _json_block(out)
    assert err_block.get("stage") == "compaction", err_block
    assert err_block.get("status") == "error", err_block
