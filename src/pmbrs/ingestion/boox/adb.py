"""ADB transport + BoOX file system collector (ADR-019 D5).

All device access goes through the ``adb`` CLI via ``subprocess`` with hard
timeouts and one retry — the NoteAir3's e-ink ADB shell is slow (recon-notes
§"Device & access"), so every call is bounded and retried exactly once.

Only *external* storage is touched (``/storage/emulated/0``) — no root paths,
no private app data, no writes to the device. This module is read-only toward
the Boox.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXTERNAL_ROOT = "/storage/emulated/0"
NOTE_DOC_TREE = f"{EXTERNAL_ROOT}/.ksync/document"
COVER_THUMB_DIR = f"{EXTERNAL_ROOT}/.noteCache/thumbnail"
PAGE_THUMB_DIR = f"{EXTERNAL_ROOT}/.noteCache/thumbnail/page"

_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


def png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Read (w, h) from a PNG's IHDR chunk. Returns (0, 0) if not parseable."""
    i = png_bytes.find(b"IHDR")
    if i < 0 or i + 12 > len(png_bytes):
        return (0, 0)
    w, h = struct.unpack(">II", png_bytes[i + 4 : i + 12])
    return (w, h)


@dataclass
class PngFile:
    """A pulled page image with its identifying facts."""

    local_path: Path
    remote_rel: str  # relative to the device external root
    sha256: str
    dims: tuple[int, int]
    size_bytes: int


class AdbError(RuntimeError):
    pass


class AdbClient:
    """Thin, bounded wrapper over the ``adb`` binary for one device serial."""

    def __init__(self, serial: str, adb_bin: str = "adb", shell_timeout_s: int = 30, pull_timeout_s: int = 180) -> None:
        self.serial = serial
        self.adb_bin = adb_bin
        self.shell_timeout_s = shell_timeout_s
        self.pull_timeout_s = pull_timeout_s

    # -- low-level ------------------------------------------------------

    def _run(self, args: list[str], timeout: int, retries: int = 1) -> str:
        cmd = [self.adb_bin, "-s", self.serial] + args
        last_err: Exception | None = None
        for _ in range(retries + 1):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if proc.returncode == 0:
                    return proc.stdout
                last_err = AdbError(f"adb {' '.join(args)} rc={proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]}")
            except subprocess.TimeoutExpired as exc:
                last_err = exc
            except FileNotFoundError as exc:
                raise AdbError(f"adb binary not found: {self.adb_bin}") from exc
        raise AdbError(f"adb failed after retries: {last_err}")

    def device_available(self) -> bool:
        if shutil.which(self.adb_bin) is None:
            return False
        try:
            out = self._run(["devices"], timeout=10, retries=0)
        except AdbError:
            return False
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == self.serial and parts[1] == "device":
                return True
        return False

    def shell(self, command: str) -> str:
        return self._run(["shell", command], timeout=self.shell_timeout_s).strip()

    def file_exists(self, remote_path: str) -> bool:
        out = self.shell(f"[ -e {remote_path} ] && echo yes")
        return "yes" in out

    def dir_listing(self, remote_dir: str) -> list[str]:
        out = self.shell(f"ls {remote_dir} 2>/dev/null")
        return [line.strip() for line in out.splitlines() if line.strip()]

    def find_pngs(self, remote_dir: str) -> list[str]:
        out = self.shell(f"find {remote_dir} -name '*.png' -type f 2>/dev/null")
        return [line.strip() for line in out.splitlines() if line.strip()]

    def pull(self, remote_path: str, local_path: Path) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(["pull", remote_path, str(local_path)], timeout=self.pull_timeout_s)
        if not local_path.exists():
            raise AdbError(f"adb pull reported success but {local_path} missing")
        return local_path

    # -- derived --------------------------------------------------------

    def sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()


class BooxCollector:
    """Read-only enumeration of BoOX notes + renders over ADB.

    Stage 1 page resolution (per stage1-spec.md §C2): the **cover thumbnail**
    ``.noteCache/thumbnail/<uuid>.png`` is the page source for every note —
    it is the reliable per-note render in shared storage. Global page dirs under
    ``thumbnail/page/`` are *not* (yet) mappable to notes without the private
    app DB, so multi-page fan-out is deferred (stage1-spec "Deferred", ADR-019
    consequences). The hook :meth:`resolve_pages` keeps the mapping point stable.
    """

    def __init__(self, adb: AdbClient) -> None:
        self.adb = adb
        self.model_name = "NoteAir3"  # pinned in recon-notes; refreshable via adb getprop
        self.transport_name = "adb"    # artifact provenance

    def list_notes(self) -> list[str]:
        """Note UUIDs (32-hex dir names) under the note document tree."""
        entries = self.adb.dir_listing(NOTE_DOC_TREE)
        return [entry for entry in entries if _UUID_RE.match(entry)]

    def note_dir_mtime_ms(self, note_uuid: str) -> int:
        """Best-effort mtime (device clock, ms epoch) of the note dir."""
        remote = f"{NOTE_DOC_TREE}/{note_uuid}"
        try:
            out = self.adb.shell(f"stat -c %Y {remote} 2>/dev/null")
            return int(out.splitlines()[0]) * 1000 if out.splitlines() and out.splitlines()[0].strip().isdigit() else 0
        except AdbError:
            return 0

    def resolve_pages(self, note_uuid: str) -> list[tuple[str, str, int]]:
        """Return [(page_id, png_remote_path, page_order)] for a note.

        Stage 1: single cover page. Kept as a method so the Stage-2
        note→page-map decode (``virtual/page/pb``) lands in one place.
        """
        cover = f"{COVER_THUMB_DIR}/{note_uuid}.png"
        if not self.adb.file_exists(cover):
            return []
        return [(note_uuid, cover, 1)]

    def pull_page(self, page_id: str, remote_path: str, workdir: Path) -> PngFile:
        local = workdir / f"{page_id}.png"
        self.adb.pull(remote_path, local)
        data = local.read_bytes()
        return PngFile(
            local_path=local,
            remote_rel=remote_path,
            sha256=self.adb.sha256_file(local),
            dims=png_dimensions(data),
            size_bytes=len(data),
        )
