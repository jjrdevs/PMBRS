#!/usr/bin/env python3
"""Simple test runner that discovers and runs functions named `test_*` in
the `tests/` package. This avoids requiring `pytest` in restricted envs.
"""
import importlib.util
import inspect
import sys
from pathlib import Path


def discover_test_modules(tests_dir: Path):
    for p in sorted(tests_dir.glob("test_*.py")):
        yield p


def run_tests(tests_dir: Path) -> int:
    failed = 0
    # Ensure repo root is on sys.path so tests can import local packages like `scripts`.
    repo_root = tests_dir.resolve().parents[0]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    for mod_path in discover_test_modules(tests_dir):
        spec = importlib.util.spec_from_file_location(mod_path.stem, str(mod_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("test_"):
                try:
                    fn()
                    print(f"{mod_path.name}::{name} OK")
                except Exception as e:
                    failed += 1
                    print(f"{mod_path.name}::{name} FAILED: {e}")
    return failed


def main():
    repo_root = Path(__file__).resolve().parents[1]
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        print("No tests/ directory found")
        sys.exit(2)
    failed = run_tests(tests_dir)
    if failed:
        print(f"{failed} test(s) failed")
        sys.exit(1)
    print("All tests passed")


if __name__ == "__main__":
    raise SystemExit(main())
