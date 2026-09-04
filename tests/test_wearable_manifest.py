"""Wearable sync manifest (ADR-021 D2/D4/D5) idempotency contract tests."""
from __future__ import annotations
import json
import os
from pmbrs.ingestion.wearable.manifest import (
    STATUS_EMPTY, STATUS_ERROR, STATUS_PROCESSED, WearableSyncManifest,
)

def _mark(m, export="ex", rel="r", sha="abc", records=3, status=STATUS_PROCESSED):
    m.mark(export=export, rel_path=rel, sha256=sha, by=100, records=records,
           windows=2, status=status, now_ms=1700000000000, error="")

class TestInitialState:
    def test_fresh_needs_processing(self):
        m = WearableSyncManifest.load("does-not-exist.json")
        assert m.exports == {}
        assert m.needs_processing(export="ex", rel_path="r", sha256="abc") is True

class TestMark:
    def test_populates_entry(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="f1", sha="s1", records=5)
        e = m.entry("ex", "f1")
        assert e.sha256 == "s1" and e.records_emitted == 5
        assert e.status == STATUS_PROCESSED and e.window_count == 2

    def test_missing_entry_none(self):
        assert WearableSyncManifest.load("x.json").entry("ex", "zzz") is None

    def test_overwrites_prior(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="f1", sha="old", records=1, status=STATUS_EMPTY)
        _mark(m, rel="f1", sha="new", records=9, status=STATUS_PROCESSED)
        e = m.entry("ex", "f1")
        assert e.sha256 == "new" and e.records_emitted == 9

    def test_error_recorded(self):
        m = WearableSyncManifest.load("x.json")
        m.mark(export="ex", rel_path="bad", sha256="", by=0, records=0,
               windows=0, status=STATUS_ERROR, now_ms=1, error="ValueError: boom")
        assert m.entry("ex", "bad").status == STATUS_ERROR
        assert m.entry("ex", "bad").error == "ValueError: boom"

class TestNeedsProcessing:
    def test_unchanged_sha_is_false(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="r", sha="SAME")
        assert m.needs_processing(export="ex", rel_path="r", sha256="SAME") is False

    def test_changed_sha_is_true(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="r", sha="OLD")
        assert m.needs_processing(export="ex", rel_path="r", sha256="NEW") is True

    def test_empty_stored_sha_is_true(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="r", sha="")
        assert m.needs_processing(export="ex", rel_path="r", sha256="ABC") is True

    def test_force_overrides_match(self):
        m = WearableSyncManifest.load("x.json")
        _mark(m, rel="r", sha="X")
        assert m.needs_processing(export="ex", rel_path="r", sha256="X", force=True) is True
        assert m.needs_processing(export="ex", rel_path="r", sha256="X") is False

class TestPersistence:
    def test_save_load_round_trip(self, tmp_path):
        p = tmp_path / "m.json"
        m = WearableSyncManifest.load(str(p))
        _mark(m, rel="r1", sha="a", records=4)
        m.last_run_ms = 42
        m.save()
        m2 = WearableSyncManifest.load(str(p))
        assert m2.last_run_ms == 42
        e = m2.entry("ex", "r1")
        assert e.sha256 == "a" and e.records_emitted == 4
        on_disk = json.loads(p.read_text())
        assert on_disk["schemaVersion"] == "1.0"
        assert on_disk["exports"]["ex"]["r1"]["sha256"] == "a"

    def test_save_creates_dirs(self, tmp_path):
        p = tmp_path / "deep" / "nested" / "m.json"
        m = WearableSyncManifest.load(str(p))
        _mark(m)
        m.save()
        assert p.exists()

    def test_atomic_write_no_tmp_leftover(self, tmp_path):
        p = tmp_path / "m.json"
        m = WearableSyncManifest.load(str(p)); _mark(m); m.save()
        leftovers = [w for w in os.listdir(str(tmp_path)) if w.endswith(".tmp")]
        assert leftovers == []
