#!/usr/bin/env python3
"""PMBRS wearable compaction CLI.

Runs the compaction pipeline over the wearable canonical windows in the raw
store and writes rollup artifacts + flat parquet exports.

Examples:
  # Default spans (5m/1h/1d) over the real store
  python scripts/pmbrs_compact_wearable.py

  # 5m + 30m + 1h spans, quiet JSON summary
  python scripts/pmbrs_compact_wearable.py --spans 5m,30m,1h --json

  # Explicit store root (test / ephemeral)
  python scripts/pmbrs_compact_wearable.py --raw-root /tmp/sandbox/store/raw
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from pmbrs.compaction import DEFAULT_SPANS, compact  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compact wearable canonical windows into rollups + parquet.")
    parser.add_argument(
        "--raw-root",
        default=None,
        help="Raw store root (default: ~/.pmbrs-private/store/raw)",
    )
    parser.add_argument(
        "--out",
        default=None,
        dest="out_dir",
        help="Parquet output dir (default: <store>/data)",
    )
    parser.add_argument(
        "--spans",
        default=",".join(DEFAULT_SPANS),
        help=f"Comma list of span names: {','.join(DEFAULT_SPANS)} or <secs>s (default: {','.join(DEFAULT_SPANS)})",
    )
    parser.add_argument("--min-coverage", type=float, default=0.5, help="Per-modality coverage floor for 'partial' (default 0.5)")
    parser.add_argument("--source", default="mobile", help="Raw-store source dir with canonical windows (default: mobile)")
    parser.add_argument("--device-alias", default="", help="Optional device alias for provenance (default: inferred)")
    parser.add_argument("--no-parquet", action="store_true", help="Skip parquet export (rollups only)")
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary and exit")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    raw_root = Path(args.raw_root).expanduser() if args.raw_root else Path.home() / ".pmbrs-private" / "store" / "raw"
    spans = [s.strip() for s in args.spans.split(",") if s.strip()]

    stats = compact(
        raw_root=raw_root,
        out_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
        spans=spans,
        min_coverage=args.min_coverage,
        source=args.source,
        device_alias=args.device_alias,
        parquet=not args.no_parquet,
    )

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2, sort_keys=True))
    else:
        d = stats.to_dict()
        print(f"compact: {d['windows_loaded']} windows -> {d['rollups_built']} rollups "
              f"({len(d['spans'])} spans: {', '.join(d['spans']) or 'none'})")
        print(f"  rollup_root : {d['rollup_root']}")
        print(f"  rollup_files: {len(d['rollup_files'])}")
        print(f"  parquet     : {d['parquet']['ok']}"
              + (f"  windows={d['parquet']['windows_parquet']} rollups={d['parquet']['rollups_parquet']}" if d['parquet']['ok'] else ""))
        if d["partial_rollups"]:
            print(f"  partial     : {d['partial_rollups']} rollups flagged partial (coverage < {args.min_coverage})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
