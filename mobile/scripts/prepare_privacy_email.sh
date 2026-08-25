#!/usr/bin/env bash
# Prepare privacy signoff package and print a ready-to-send email template
# Usage: ./scripts/prepare_privacy_email.sh [output-zip]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
OUT_ZIP=${1:-"$ROOT/mobile_privacy_signoff_$(date +%Y%m%d_%H%M%S).zip"}

echo "Creating privacy signoff package: $OUT_ZIP"
"$SCRIPT_DIR/package_privacy_signoff.sh" "$OUT_ZIP"

EMAIL_PATH="$ROOT/docs/privacy/privacy_email_draft.md"

echo
echo "=== Privacy package created: $OUT_ZIP ==="
echo
if [ -f "$EMAIL_PATH" ]; then
  echo "Email draft (copy/paste):"
  echo "----------------------------------------"
  sed -n '1,200p' "$EMAIL_PATH"
  echo "----------------------------------------"
fi

echo
echo "Suggested command to attach and send via mutt (if available):"
echo
echo "mutt -s \"Request for privacy review — PMBRS mobile collector\" -a $OUT_ZIP -- privacy-team@example.com < $EMAIL_PATH"
echo
echo "Or attach $OUT_ZIP to your preferred mail client and send to privacy reviewers."
