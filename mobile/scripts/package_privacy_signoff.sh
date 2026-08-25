#!/usr/bin/env bash
# Package privacy signoff documents into a zip for reviewers
# Usage: ./scripts/package_privacy_signoff.sh [output-zip]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
OUT=${1:-"$ROOT/mobile_privacy_signoff_$(date +%Y%m%d_%H%M%S).zip"}

echo "Packaging privacy signoff into $OUT"

tmpdir=$(mktemp -d)
cp "$ROOT/docs/privacy/mobile-privacy-signoff.md" "$tmpdir/" 2>/dev/null || true
cp "$ROOT/docs/privacy/privacy_signoff_package.md" "$tmpdir/" 2>/dev/null || true
cp "$ROOT/mobile/HANDOFF.md" "$tmpdir/" 2>/dev/null || true
cp "$ROOT/mobile/OBSERVABILITY.md" "$tmpdir/" 2>/dev/null || true
mkdir -p "$tmpdir/sample_exports"
echo "(Please attach a sample pmbrs_telemetry.xml manually or place it in sample_exports)" > "$tmpdir/README.txt"

pushd "$tmpdir" >/dev/null
zip -r "$OUT" . >/dev/null
popd >/dev/null

rm -rf "$tmpdir"
echo "Created $OUT"
