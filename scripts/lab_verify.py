#!/usr/bin/env python3
"""Live lab verification (T-010/T-011). Runs inside WSL against a running lab.

Checks, in order (spec success criteria). The drill runs FIRST on a pristine
lab so the backup differs from the wave's changes; restore then proves a real
undo, not a no-op:
  1 drill    forced post-check failure exits non-zero AND every host logs
             "restore verified" (restored state == pristine backup)
  2 deploy   live wave exits 0 (post-check = drift rc 0 per host)
  3 rerun    second live wave exits 0 with changed=0 on every lab host
Exit 0 only when all checks pass. Output is the evidence for reports/.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys

RECAP = re.compile(r"^(\S+)\s+:\s+ok=\d+\s+changed=(\d+)", re.M)
HOSTS = ("lab-sw01", "lab-sw02")


def changed_counts(recap: str) -> dict[str, int]:
    return {host: int(n) for host, n in RECAP.findall(recap)}


def idempotent(counts: dict[str, int]) -> bool:
    return all(counts.get(h) == 0 for h in HOSTS)


def play(inventory: str, wave: str, extra: list[str]) -> subprocess.CompletedProcess:
    cmd = ["ansible-playbook", "playbooks/deploy/site.yml", "-i", inventory,
           "-e", "netaut_mode=live", "-e", f"netaut_wave={wave}", *extra]
    env = dict(os.environ, ANSIBLE_ROLES_PATH="roles")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live waves against the lab.")
    parser.add_argument("--inventory", default="inventories/lab-eos.yml")
    parser.add_argument("--wave", required=True)
    parser.add_argument("--vault-args", default="",
                        help="extra ansible args, e.g. '-e @vault.yml --vault-password-file f'")
    args = parser.parse_args(argv)
    extra = shlex.split(args.vault_args)
    results: list[tuple[str, bool, str]] = []

    drill = play(args.inventory, f"{args.wave}-a",
                 extra + ["-e", "netaut_force_postcheck_fail=true"])
    restored = all(f"restore verified for {h}" in drill.stdout for h in HOSTS)
    results.append(("drill", drill.returncode != 0 and restored,
                    f"rc={drill.returncode} restore_verified={restored}"))

    first = play(args.inventory, f"{args.wave}-b", extra)
    results.append(("deploy", first.returncode == 0, f"rc={first.returncode}"))

    second = play(args.inventory, f"{args.wave}-c", extra)
    counts = changed_counts(second.stdout)
    results.append(("rerun", second.returncode == 0 and idempotent(counts),
                    f"rc={second.returncode} changed={counts}"))

    for name, ok, detail in results:
        print(f"{name}: {'PASS' if ok else 'FAIL'} ({detail})")
    if not all(ok for _, ok, _ in results):
        for proc in (drill, first, second):
            print(proc.stdout[-4000:])
        print("lab-verify FAILED")
        return 1
    print("lab-verify OK: all live checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
