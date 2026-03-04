#!/usr/bin/env python3
"""
Clara Pipeline — Diff viewer: compare v1 and v2 for any account.
Usage: python diff_viewer.py <account_id>
"""

import json
import sys
from pathlib import Path

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs" / "accounts"

RESET  = "\033[0m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"

def load(path):
    with open(path) as f:
        return json.load(f)

def fmt(val):
    if val is None:
        return "(empty)"
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else "(empty list)"
    if isinstance(val, dict):
        return json.dumps(val, indent=2)
    return str(val)

def diff_dicts(v1, v2, prefix=""):
    all_keys = set(v1.keys()) | set(v2.keys())
    changes = []
    for key in sorted(all_keys):
        full_key = f"{prefix}.{key}" if prefix else key
        a = v1.get(key)
        b = v2.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            changes.extend(diff_dicts(a, b, full_key))
        elif a != b:
            changes.append((full_key, a, b))
    return changes

def main():
    if len(sys.argv) < 2:
        print("Usage: python diff_viewer.py <account_id>")
        sys.exit(1)

    account_id = sys.argv[1]
    v1_path = OUTPUTS_DIR / account_id / "v1" / "account_memo.json"
    v2_path = OUTPUTS_DIR / account_id / "v2" / "account_memo.json"
    cl_path = OUTPUTS_DIR / account_id / "changelog.json"

    if not v1_path.exists():
        print(f"✗ v1 memo not found: {v1_path}")
        sys.exit(1)
    if not v2_path.exists():
        print(f"✗ v2 memo not found: {v2_path}")
        sys.exit(1)

    v1 = load(v1_path)
    v2 = load(v2_path)

    print(f"\n{BOLD}{CYAN}=== Clara Diff Viewer ==={RESET}")
    print(f"Account : {account_id}")
    print(f"Company : {v2.get('company_name', '?')}")
    print()

    skip = {"version", "generated_at", "source"}
    changes = [(k, a, b) for k, a, b in diff_dicts(v1, v2) if k not in skip]

    if not changes:
        print(f"{GREEN}✓ No changes between v1 and v2.{RESET}")
    else:
        print(f"{BOLD}Changes ({len(changes)} fields):{RESET}\n")
        for field, old_val, new_val in changes:
            print(f"  {BOLD}{field}{RESET}")
            print(f"    {RED}— v1: {fmt(old_val)}{RESET}")
            print(f"    {GREEN}+ v2: {fmt(new_val)}{RESET}")
            print()

    if cl_path.exists():
        cl = load(cl_path)
        print(f"{YELLOW}Changelog saved at: {cl_path}{RESET}")
        print(f"Total logged changes: {cl.get('total_changes', '?')}")

if __name__ == "__main__":
    main()
