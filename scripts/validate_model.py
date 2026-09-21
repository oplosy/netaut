#!/usr/bin/env python3
"""Intended-state schema validator, canonical version (T-005, REQ-001).

Promotes the interim T-001 check into its specified home. Enforces
netbox/schema.yml rules: required top-level keys, reference integrity
(site/vrf/vlan/prefix), VLAN range, CIDR/IP validity, non-empty common
server lists. Exit 0 clean, 1 violations.
"""
from __future__ import annotations

import argparse
import ipaddress
import sys

import yaml


def validate(schema: dict, data: dict) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required_top_level", []):
        if key not in data:
            errors.append(f"missing top-level key: {key}")

    sites = {s.get("name") for s in data.get("sites", [])}
    vrfs = {v.get("name") for v in data.get("vrfs", []) if "name" in v and "rd" in v}
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
        vlans.setdefault(vid, v.get("name"))

    for p in data.get("prefixes", []):
        try:
            ipaddress.ip_network(p.get("prefix"))
        except (ValueError, TypeError):
            errors.append(f"invalid prefix: {p}")
            continue
        if p.get("vlan") not in vlans:
            errors.append(f"prefix {p.get('prefix')} references unknown vlan")
        if p.get("vrf") not in vrfs:
            errors.append(f"prefix {p.get('prefix')} references unknown vrf")

    for d in data.get("devices", []):
        name = d.get("name", "?")
        for req in schema.get("rules", {}).get("devices", {}).get("required", []):
            if req not in d:
                errors.append(f"device {name} missing: {req}")
        if d.get("site") not in sites:
            errors.append(f"device {name} references unknown site")
        allowed = schema.get("rules", {}).get("devices", {}).get("platform_allowed", [])
        if allowed and d.get("platform") not in allowed:
            errors.append(f"device {name} has disallowed platform")
        for iface in d.get("interfaces", []):
            if "name" not in iface:
                errors.append(f"device {name} interface missing name")
            if iface.get("access_vlan") not in vlans:
                errors.append(f"device {name} references unknown vlan")
        for key in ("ntp_servers", "dns_servers", "syslog_servers"):
            vals = (d.get("common", {}) or {}).get(key, [])
            if not vals:
                errors.append(f"device {name} common.{key} empty")
            for v in vals:
                try:
                    ipaddress.ip_address(v)
                except ValueError:
                    errors.append(f"device {name} common.{key} not an IP: {v}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate intended state against schema.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.schema, encoding="utf-8") as f:
            schema = yaml.safe_load(f)
        with open(args.input, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        print(f"validate ERROR: {exc}")
        return 1
    errors = validate(schema, data)
    if errors:
        print(f"validate FAILED: {len(errors)} violation(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("validate OK: intended state satisfies schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
