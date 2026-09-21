#!/usr/bin/env python3
"""Routing policy check (T-007, INV-005).

Validates static routing sections of intended state: CIDR/IP shapes and,
critically, that every route-map prefix-list reference resolves to a defined
prefix-list. Only stdlib + PyYAML are imported (no device contact possible).

Exit codes: 0 = clean, 1 = violations.
"""
from __future__ import annotations

import argparse
import ipaddress
import sys

import yaml


def check(data: dict) -> list[str]:
    errors: list[str] = []
    for r in data.get("static_routes", []):
        try:
            ipaddress.ip_network(r.get("prefix"))
        except (ValueError, TypeError):
            errors.append(f"static route invalid prefix: {r}")
        try:
            ipaddress.ip_address(r.get("next_hop"))
        except (ValueError, TypeError):
            errors.append(f"static route invalid next-hop: {r}")

    defined = set()
    for pl in data.get("prefix_lists", []):
        if "name" not in pl:
            errors.append(f"prefix-list missing name: {pl}")
            continue
        defined.add(pl["name"])
        for s in pl.get("sequences", []):
            if not isinstance(s.get("seq"), int):
                errors.append(f"prefix-list {pl['name']} seq not an integer: {s}")
            if s.get("action") not in ("permit", "deny"):
                errors.append(f"prefix-list {pl['name']} bad action: {s}")
            try:
                ipaddress.ip_network(s.get("prefix"))
            except (ValueError, TypeError):
                errors.append(f"prefix-list {pl['name']} invalid prefix: {s}")

    for rm in data.get("route_maps", []):
        if "name" not in rm:
            errors.append(f"route-map missing name: {rm}")
        for s in rm.get("sequences", []):
            if not isinstance(s.get("seq"), int):
                errors.append(f"route-map {rm.get('name')} seq not an integer: {s}")
            if s.get("action") not in ("permit", "deny"):
                errors.append(f"route-map {rm.get('name')} bad action: {s}")
            ref = s.get("match_prefix_list")
            if ref not in defined:
                errors.append(
                    f"route-map {rm.get('name')} seq {s.get('seq')} references "
                    f"undefined prefix-list: {ref}"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed routing policy check.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        print(f"policy-check ERROR: {exc}")
        return 1
    errors = check(data)
    if errors:
        print(f"policy-check FAILED: {len(errors)} violation(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("policy-check OK: references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
