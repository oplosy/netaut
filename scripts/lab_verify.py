#!/usr/bin/env python3
"""Live lab verification (T-010/T-011, T-014/T-015). Runs inside WSL against a running lab.

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
import socket
import subprocess
import sys
import time

import yaml

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


def inventory_hosts(path) -> dict[str, str]:
    """Host -> ansible_host from a YAML inventory, walking nested children."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    found: dict[str, str] = {}

    def walk(group: dict) -> None:
        for name, hvars in (group.get("hosts") or {}).items():
            found[name] = (hvars or {}).get("ansible_host", name)
        for child in (group.get("children") or {}).values():
            walk(child or {})

    walk(data.get("all", {}))
    return found


def wait_ready(addrs: dict[str, str], port: int, timeout: float,
               connect=socket.create_connection, sleep=time.sleep,
               clock=time.monotonic) -> list[str]:
    """Poll each host's TCP port until it accepts or timeout; return the rest."""
    pending = dict(addrs)
    deadline = clock() + timeout
    while pending:
        for name, addr in list(pending.items()):
            try:
                connect((addr, port), timeout=3).close()
                del pending[name]
            except OSError:
                pass
        if not pending or clock() >= deadline:
            break
        sleep(5)
    return sorted(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live waves against the lab.")
    parser.add_argument("--inventory", default="inventories/lab-eos.yml")
    parser.add_argument("--wave", required=True)
    parser.add_argument("--vault-args", default="",
                        help="extra ansible args, e.g. '-e @vault.yml --vault-password-file f'")
    parser.add_argument("--wait-port", type=int, default=0,
                        help="TCP port that must answer on every host before any play (0 = no wait)")
    parser.add_argument("--wait-seconds", type=float, default=300)
    parser.add_argument("--image", default="", help="lab image, recorded in the evidence")
    args = parser.parse_args(argv)
    if args.image:
        print(f"image: {args.image}")
    if args.wait_port:
        left = wait_ready(inventory_hosts(args.inventory), args.wait_port, args.wait_seconds)
        if left:
            print(f"not ready: {', '.join(left)} (port {args.wait_port}); no wave started")
            print("lab-verify FAILED")
            return 1
        print(f"ready: all hosts answer on port {args.wait_port}")
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
