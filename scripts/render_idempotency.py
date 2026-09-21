#!/usr/bin/env python3
"""Render-idempotency proof, canonical version (T-005, REQ-005).

Promotes the interim T-002 check into its specified home. Renders every
device in --input through templates/<vendor>/vlan_interface.j2 twice and
fails when any byte differs. Exit 0 identical, 1 mismatch/error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jinja2
import yaml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove render idempotency per device.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--vendor", default="ios")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    try:
        data = yaml.safe_load((repo / args.input).read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"render-idempotency ERROR: {exc}")
        return 1
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(repo / "templates" / args.vendor)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    try:
        template = env.get_template("vlan_interface.j2")
    except jinja2.TemplateNotFound as exc:
        print(f"render-idempotency ERROR: {exc}")
        return 1

    ok = True
    for device in data.get("devices", []):
        context = {"netaut_vlans": data.get("vlans", []),
                   "netaut_interfaces": device.get("interfaces", [])}
        first, second = template.render(context).encode(), template.render(context).encode()
        status = "IDENTICAL" if first == second else "DIFFERS"
        print(f"{device.get('name')}: {status} ({len(first)} bytes)")
        ok = ok and first == second
    if not ok:
        print("render-idempotency FAILED")
        return 1
    print("render-idempotency OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
