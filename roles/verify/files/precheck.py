#!/usr/bin/env python3
"""Offline intended-state conflict gate (T-003, REQ-003).

Reads one intended-state YAML file from local disk and exits non-zero when
IP/VLAN/reference conflicts exist. Makes zero network connections by design:
only stdlib + PyYAML are imported (enforced by test_precheck.py). Deploy plays
run this BEFORE any device task, so a conflict aborts with no SSH opened.
"""
from __future__ import annotations

import argparse
import ipaddress
import sys

import yaml


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level mapping required")
    return data


def check(data: dict) -> list[str]:
    errors: list[str] = []

    sites = {s.get("name") for s in data.get("sites", [])}
    vrfs: dict[str, dict] = {}
    for v in data.get("vrfs", []):
        if "name" not in v or "rd" not in v:
            errors.append(f"vrf missing name/rd: {v}")
            continue
        vrfs[v["name"]] = v

    vlans: dict[int, str] = {}
    for v in data.get("vlans", []):
        try:
            vid = int(v.get("id"))
        except (TypeError, ValueError):
            errors.append(f"vlan id not an integer: {v}")
            continue
        if not 1 <= vid <= 4094:
            errors.append(f"vlan id out of range 1-4094: {v}")
        if v.get("vrf") not in vrfs:
            errors.append(f"vlan {vid} references unknown vrf: {v.get('vrf')}")
        if vid in vlans and vlans[vid] != v.get("name"):
            errors.append(
                f"vlan {vid} has conflicting names: {vlans[vid]!r} vs {v.get('name')!r}"
            )
        vlans.setdefault(vid, v.get("name"))

    networks: list = []
    for p in data.get("prefixes", []):
        try:
            net = ipaddress.ip_network(p.get("prefix"))
        except (ValueError, TypeError):
            errors.append(f"invalid prefix: {p}")
            continue
        for other in networks:
            if net.overlaps(other):
                errors.append(f"overlapping prefixes: {net} vs {other}")
        networks.append(net)
        if p.get("vlan") not in vlans:
            errors.append(f"prefix {net} references unknown vlan: {p.get('vlan')}")
        if p.get("vrf") not in vrfs:
            errors.append(f"prefix {net} references unknown vrf: {p.get('vrf')}")

    seen_devices: set[str] = set()
    for d in data.get("devices", []):
        name = d.get("name", "?")
        if name in seen_devices:
            errors.append(f"duplicate device name: {name}")
        seen_devices.add(name)
        if d.get("site") not in sites:
            errors.append(f"device {name} references unknown site: {d.get('site')}")
        seen_ifaces: set[str] = set()
        for iface in d.get("interfaces", []):
            if iface.get("name") in seen_ifaces:
                errors.append(f"device {name} duplicate interface: {iface.get('name')}")
            seen_ifaces.add(iface.get("name"))
            if iface.get("access_vlan") not in vlans:
                errors.append(
                    f"device {name} interface {iface.get('name')} "
                    f"references unknown vlan: {iface.get('access_vlan')}"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed pre-deploy conflict gate.")
    parser.add_argument("--input", required=True, help="intended-state YAML file")
    args = parser.parse_args(argv)
    try:
        errors = check(load(args.input))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"precheck ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        print(f"precheck FAILED: {len(errors)} conflict(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("precheck OK: no conflicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
