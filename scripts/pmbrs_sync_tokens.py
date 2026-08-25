#!/usr/bin/env python3
"""PMBRS sync-token CLI (Stage-3 Phase 0, ADR-020 D2).

Usage:
    pmbrs_sync_tokens.py issue   ROLE [--label L] [--note N]
    pmbrs_sync_tokens.py show    [ROLE_OR_LABEL]
    pmbrs_sync_tokens.py revoke  ROLE_OR_LABEL
    pmbrs_sync_tokens.py list

Roles: boox | mobile | dev. Issue/revoke are idempotent-ish: issuing under an
existing label replaces the record for that label (token secret is new either
way; the *old* secret is moved to the revoked list so an old device keeps
working until re-provisioned is a deliberate choice you make with revoke).
The full secret is printed exactly once, at issue time.

File:  ~/.pmbrs-private/config/sync_tokens.json  (chmod 600)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pmbrs.auth import DEFAULT_TOKENS_PATH, SyncTokenStore  # noqa: E402


def _print_token(tok) -> None:
    print(tok.secret)


def main() -> int:
    p = argparse.ArgumentParser(description="PMBRS sync-bearer-token management")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("issue", help="issue a new token for a role")
    pi.add_argument("role", choices=["boox", "mobile", "dev"])
    pi.add_argument("--label", default=None, help="human label (default: role)")
    pi.add_argument("--note", default="", help="freeform note stored with the token")

    pr = sub.add_parser("revoke", help="revoke an active token by label or role")
    pr.add_argument("label_or_role")

    sub.add_parser("list", help="show active + revoked tokens (secrets redacted)")
    p.add_argument("--show-secrets", action="store_true", help="print full token secrets instead of redacting (list/show only)")
    ss = sub.add_parser("show", help="show active tokens for a role/label (secrets redacted)")
    ss.add_argument("role_or_label", nargs="?")

    a = p.parse_args()
    store = SyncTokenStore(DEFAULT_TOKENS_PATH)

    if a.cmd == "issue":
        tok = store.issue(a.role, label=a.label, note=a.note)
        _print_token(tok)
        print(
            f"[issued] role={tok.role} label={tok.label} "
            f"path={DEFAULT_TOKENS_PATH}  (SECRET ABOVE — store it on the device NOW; "
            "it is not recoverable later)",
            file=sys.stderr,
        )
        return 0

    if a.cmd == "revoke":
        ok = store.revoke(a.label_or_role)
        if not ok:
            print(f"[no-op] no active token with label/role {a.label_or_role!r}", file=sys.stderr)
            return 1
        print(f"[revoked] {a.label_or_role}", file=sys.stderr)
        return 0

    active = store.list_active()
    if a.cmd == "list":
        if not active:
            print("(no active tokens)", file=sys.stderr)
            return 0
        for t in active:
            secret = t["secret"] if a.show_secrets else f"{t['secret'][:8]}…({len(t['secret'])} chars)"
            print(f"{t['role']:<8} {t['label']:<10} {secret:<30} {t['created_at']}  note={t['note']!r}")
        return 0

    # show
    sel = [t for t in active if not a.role_or_label or t["role"] == a.role_or_label or t["label"] == a.role_or_label]
    if not sel:
        print(f"(no active tokens match {a.role_or_label!r})", file=sys.stderr)
        return 0
    for t in sel:
        secret = t["secret"] if a.show_secrets else f"{t['secret'][:8]}…({len(t['secret'])} chars)"
        print(f"{t['role']:<8} {t['label']:<10} {secret:<30} sha256_12={t['sha256_12']} {t['created_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
