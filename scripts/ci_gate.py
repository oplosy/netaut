#!/usr/bin/env python3
"""Local CI gate chain (T-005, OPS-002).

Runs every merge gate that can execute on this host, in dependency order:
workflow validity, secret scan, model validation, render idempotency, full
pytest suite. Ansible-side gates (syntax-check, --check dry runs) execute in
the GitHub Actions Linux job; they were proven via WSL during T-000..T-004.
Exit 0 only when every step passes.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def run(cmd: list[str], root: Path) -> int:
    print(f"+ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=root)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local CI gate chain.")
    parser.add_argument("--sample", default="netbox/intended/sample.yml")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    failures: list[str] = []

    try:
        workflow = yaml.safe_load((root / ".github" / "workflows" / "ci.yml").read_text())
        assert isinstance(workflow.get("jobs"), dict) and workflow["jobs"], "no jobs"
        print("workflow OK: ci.yml parses with jobs:", ", ".join(workflow["jobs"]))
    except (OSError, AssertionError, yaml.YAMLError) as exc:
        failures.append(f"workflow ({exc})")

    gates = [
        ("secret-scan", [sys.executable, "scripts/secret_scan.py", "--root", "."]),
        ("validate-model", [sys.executable, "scripts/validate_model.py",
                            "--schema", "netbox/schema.yml", "--input", args.sample]),
        ("validate-model-eos", [sys.executable, "scripts/validate_model.py",
                                "--schema", "netbox/schema.yml",
                                "--input", "netbox/intended/lab-eos.yml"]),
        ("render-idempotency", [sys.executable, "scripts/render_idempotency.py",
                                "--input", args.sample, "--vendor", "ios", "--repo", "."]),
        ("pytest", [sys.executable, "-m", "pytest", "roles", "scripts/tests", "-q"]),
    ]
    for name, cmd in gates:
        if run(cmd, root) != 0:
            failures.append(name)

    if failures:
        print(f"ci-gate FAILED: {', '.join(failures)}")
        return 1
    print("ci-gate OK: all local gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
