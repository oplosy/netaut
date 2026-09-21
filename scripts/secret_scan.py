#!/usr/bin/env python3
"""Repository secret scanner (T-005, INV-001).

Walks --root, flags credential-shaped content, and exits 1 on any hit.
Output is masked by construction: only path, line number and pattern name
are printed, never file content or secret values.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

PATTERNS = [
    ("password-assignment", re.compile(r"(?i)[\w-]*(password|passwd|pwd)\b\s*[:=]\s*\S+")),
    ("secret-assignment", re.compile(r"(?i)[\w-]*secret\b\s*[:=]\s*\S+")),
    ("private-key", re.compile(r"BEGIN [A-Z0-9 ]*PRIVATE KEY")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[op]_[A-Za-z0-9_]{10,}")),
    ("slack-token", re.compile(r"xox[bap]-")),
    ("vault-password-file", re.compile(r"vault_password_file\s*=")),
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "collections", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".retry", ".log"}
TEXT_SUFFIXES = {
    ".yml", ".yaml", ".cfg", ".ini", ".txt", ".md", ".j2", ".py",
    ".json", ".toml", ".cfg", "",
}


def scannable(path: pathlib.Path) -> bool:
    if path.suffix in SKIP_SUFFIXES:
        return False
    if path.suffix in TEXT_SUFFIXES or "pass" in path.name or "secret" in path.name:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" not in chunk
    except OSError:
        return False


def scan(root: pathlib.Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not scannable(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        for lineno, line in enumerate(lines, 1):
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(root)}:{lineno} [{name}]")
                    break
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed secret scan (masked output).")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    findings = scan(pathlib.Path(args.root))
    if findings:
        print(f"secret-scan FAILED: {len(findings)} finding(s):")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("secret-scan OK: no findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
