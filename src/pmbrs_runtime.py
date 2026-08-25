#!/usr/bin/env python3
"""Local PMBRS runtime configuration and scheduling logic.

This is intentionally minimal and explicit: PMBRS owns the raw artifact store,
while Hermes may be configured to read only summary or snapshot artifacts.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = Path("/home/jjrdev/workspace/pmbrs/config/external_data_policy.json")


@dataclass
class ScheduleState:
    next_run_at_epoch_ms: int
    last_run_at_epoch_ms: int | None = None
    last_status: str = "pending"
    last_checkpoint: str | None = None


class PmbrsRuntime:
    def __init__(self, policy_path: str | Path = DEFAULT_POLICY_PATH):
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.artifact_root = Path(self.policy["artifact_root"])
        self.state_root = Path(self.policy["state_root"])
        self.checkpoint_root = Path(self.policy["checkpoint_root"])
        self.queue_root = Path(self.policy["queue_root"])
        self.raw_root = Path(self.policy["raw_root"])
        self.summary_root = Path(self.policy["summary_root"])
        self.hermes_readonly_root = Path(self.policy["hermes_readonly_root"])
        self.scheduler_state_file = Path(self.policy["scheduler_state_file"])
        self.export_snapshot_file = Path(self.policy["export_snapshot_file"])
        self._ensure_directories()

    def _load_policy(self) -> dict[str, Any]:
        with self.policy_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _ensure_directories(self) -> None:
        for path in [
            self.artifact_root,
            self.state_root,
            self.checkpoint_root,
            self.queue_root,
            self.raw_root,
            self.summary_root,
            self.hermes_readonly_root,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def load_schedule_state(self) -> ScheduleState:
        if not self.scheduler_state_file.exists():
            return ScheduleState(next_run_at_epoch_ms=0, last_run_at_epoch_ms=None, last_status="new")

        with self.scheduler_state_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return ScheduleState(
            next_run_at_epoch_ms=int(data.get("next_run_at_epoch_ms", 0)),
            last_run_at_epoch_ms=data.get("last_run_at_epoch_ms"),
            last_status=data.get("last_status", "pending"),
            last_checkpoint=data.get("last_checkpoint"),
        )

    def save_schedule_state(self, state: ScheduleState) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        payload = asdict(state)
        with self.scheduler_state_file.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")

    def advance_schedule(self, now_ms: int) -> ScheduleState:
        state = self.load_schedule_state()
        interval_ms = int(self.policy["default_schedule_minutes"]) * 60 * 1000
        if state.next_run_at_epoch_ms <= 0:
            state.next_run_at_epoch_ms = now_ms + interval_ms
        if now_ms >= state.next_run_at_epoch_ms:
            state.last_run_at_epoch_ms = now_ms
            state.last_status = "ran"
            state.last_checkpoint = f"checkpoint-{now_ms}"
            state.next_run_at_epoch_ms = now_ms + interval_ms
        self.save_schedule_state(state)
        return state

    def _collect_raw_summary(self, now_ms: int) -> dict[str, Any]:
        raw_files = []
        total_bytes = 0
        newest_epoch_ms = 0
        for path in sorted(self.raw_root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            total_bytes += stat.st_size
            raw_files.append(str(path.relative_to(self.raw_root)))
            newest_epoch_ms = max(newest_epoch_ms, int(stat.st_mtime * 1000))

        return {
            "generated_at_epoch_ms": now_ms,
            "raw_root": str(self.raw_root),
            "raw_file_count": len(raw_files),
            "raw_total_bytes": total_bytes,
            "newest_raw_file_epoch_ms": newest_epoch_ms,
            "raw_files_sample": raw_files[:20],
            "read_only": True,
            "mode": "hermes_read_only",
        }

    def write_hermes_snapshot(self, payload: dict[str, Any]) -> Path:
        self.export_snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        with self.export_snapshot_file.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return self.export_snapshot_file

    def hermes_snapshot(self) -> dict[str, Any]:
        summary_dir = self.summary_root
        raw_dir = self.raw_root
        return {
            "artifact_root": str(self.artifact_root),
            "raw_root": str(raw_dir),
            "summary_root": str(summary_dir),
            "read_only": True,
            "allowed_summary_files": sorted(str(p.relative_to(summary_dir)) for p in summary_dir.rglob("*.json"))[:50],
            "raw_data_note": "Raw artifact store is authoritative and not writable by Hermes.",
            "mode": "hermes_read_only",
        }

    def publish_summary_snapshot(self, now_ms: int | None = None) -> dict[str, Any]:
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        self.summary_root.mkdir(parents=True, exist_ok=True)
        self.hermes_readonly_root.mkdir(parents=True, exist_ok=True)

        summary_payload = self._collect_raw_summary(now_ms)
        summary_payload.update({
            "artifact_root": str(self.artifact_root),
            "summary_root": str(self.summary_root),
            "hermes_readonly_root": str(self.hermes_readonly_root),
            "raw_data_note": "Raw artifact store is authoritative and not writable by Hermes.",
        })

        summary_file = self.summary_root / f"pmbrs_summary_{now_ms}.json"
        with summary_file.open("w", encoding="utf-8") as fh:
            json.dump(summary_payload, fh, indent=2, sort_keys=True)
            fh.write("\n")

        hermes_payload = {
            **summary_payload,
            "allowed_summary_files": sorted(str(p.relative_to(self.summary_root)) for p in self.summary_root.rglob("*.json"))[:50],
        }
        snapshot_file = self.hermes_readonly_root / "pmbrs_summary.json"
        snapshot_file.chmod(0o644)
        with snapshot_file.open("w", encoding="utf-8") as fh:
            json.dump(hermes_payload, fh, indent=2, sort_keys=True)
            fh.write("\n")

        snapshot_file.chmod(0o444)
        self.write_hermes_snapshot(hermes_payload)
        return {
            "summary_file": str(summary_file),
            "snapshot_file": str(snapshot_file),
            "summary_payload": summary_payload,
            "hermes_snapshot": hermes_payload,
        }

    def run_cycle(self, now_ms: int | None = None) -> dict[str, Any]:
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        state = self.load_schedule_state()
        interval_ms = int(self.policy["default_schedule_minutes"]) * 60 * 1000
        if state.next_run_at_epoch_ms <= 0:
            state.next_run_at_epoch_ms = now_ms + interval_ms

        if now_ms >= state.next_run_at_epoch_ms:
            state.last_run_at_epoch_ms = now_ms
            state.last_status = "ran"
            state.last_checkpoint = f"checkpoint-{now_ms}"
            state.next_run_at_epoch_ms = now_ms + interval_ms

        self.save_schedule_state(state)
        publication = self.publish_summary_snapshot(now_ms)
        publication["schedule_state"] = asdict(state)
        return publication


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PMBRS runtime and Hermes summary publication")
    parser.add_argument("--run-once", action="store_true", help="run a single cycle")
    parser.add_argument("--loop", action="store_true", help="run continuously on the default interval")
    parser.add_argument("--interval-seconds", type=int, default=60, help="loop interval in seconds")
    args = parser.parse_args()

    runtime = PmbrsRuntime()
    if args.loop:
        while True:
            result = runtime.run_cycle()
            print(json.dumps({"status": "cycle_complete", "schedule_state": result["schedule_state"]}, indent=2, sort_keys=True))
            time.sleep(args.interval_seconds)
    else:
        result = runtime.run_cycle()
        print(json.dumps({"status": "cycle_complete", "schedule_state": result["schedule_state"], "snapshot_file": result["snapshot_file"]}, indent=2, sort_keys=True))
