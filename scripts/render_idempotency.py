#!/usr/bin/env python3
"""Render-idempotency proof, canonical version (T-005, REQ-005).

Promotes the interim T-002 check into its specified home. Renders every
template under templates/<vendor>/ twice for each device of that platform in
--input and fails when any byte differs (T-008: all templates, all vendors).
No matching device is an error, never a vacuous pass.
Exit 0 identical, 1 mismatch/error.
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
    vendor_dir = repo / "templates" / args.vendor
    templates = sorted(p.relative_to(vendor_dir).as_posix() for p in vendor_dir.rglob("*.j2"))
    if not templates:
        print(f"render-idempotency ERROR: no templates under {vendor_dir}")
        return 1
    devices = [d for d in data.get("devices", []) if d.get("platform") == args.vendor]
    if not devices:
        print(f"render-idempotency ERROR: no devices with platform {args.vendor} in {args.input}")
        return 1
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(vendor_dir)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    ok = True
    for device in devices:
        context = {"netaut_vlans": data.get("vlans", []),
                   "netaut_interfaces": device.get("interfaces", []),
                   "netaut_static_routes": data.get("static_routes", []),
                   "netaut_prefix_lists": data.get("prefix_lists", []),
                   "netaut_route_maps": data.get("route_maps", [])}
        for name in templates:
            template = env.get_template(name)
            first, second = template.render(context).encode(), template.render(context).encode()
            status = "IDENTICAL" if first == second else "DIFFERS"
            print(f"{device.get('name')} {name}: {status} ({len(first)} bytes)")
            ok = ok and first == second
    if not ok:
        print("render-idempotency FAILED")
        return 1
    print("render-idempotency OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
