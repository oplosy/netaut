#!/usr/bin/env python3
"""Read-only drift detector (T-004, REQ-006).

Compares an operational snapshot (side B: device-read facts) against intended
state (side A) and writes a markdown report. Never pushes config and never
modifies its inputs: only stdlib + PyYAML are imported (enforced by tests),
and the only write is the report file.

Exit codes: 0 = no drift, 2 = drift found, 1 = error.
"""
from __future__ import annotations

import argparse
import sys

import yaml


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level mapping required")
    return data


def load_json(path: str) -> dict:
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level object required")
    return data


def diff_device(name: str, intended: dict, operational: dict,
                global_vlans: dict[int, str]) -> list[str]:
    drifts: list[str] = []
    intended_vlans = global_vlans
    for v in operational.get("vlans", []):
        vid = int(v["id"])
        if vid not in intended_vlans:
            drifts.append(f"{name}: unexpected operational vlan {vid} ({v.get('name')})")
        elif intended_vlans[vid] != v.get("name"):
            drifts.append(
                f"{name}: vlan {vid} name drift: "
                f"intended {intended_vlans[vid]!r} vs operational {v.get('name')!r}"
            )
    for vid in intended_vlans:
        if vid not in {int(v["id"]) for v in operational.get("vlans", [])}:
            drifts.append(f"{name}: intended vlan {vid} missing operationally")

    intended_ifaces = {i["name"]: i.get("access_vlan") for i in intended.get("interfaces", [])}
    for i in operational.get("interfaces", []):
        if i["name"] not in intended_ifaces:
            drifts.append(f"{name}: unexpected operational interface {i['name']}")
        elif intended_ifaces[i["name"]] != i.get("access_vlan"):
            drifts.append(
                f"{name}: interface {i['name']} vlan drift: "
                f"intended {intended_ifaces[i['name']]} vs operational {i.get('access_vlan')}"
            )

    for key in ("ntp_servers", "dns_servers", "syslog_servers"):
        want = sorted((intended.get("common", {}) or {}).get(key, []))
        got = sorted((operational.get("common", {}) or {}).get(key, []))
        if want != got:
            drifts.append(f"{name}: common.{key} drift: intended {want} vs operational {got}")
    return drifts


def build_report(devices: dict[str, dict], intended: dict, drifts: list[str]) -> str:
    lines = ["# Drift report", ""]
    if not drifts:
        lines.append("NO DRIFT: operational state matches intended state.")
    else:
        lines.append(f"DRIFT FOUND: {len(drifts)} difference(s).")
        lines.append("")
        for d in drifts:
            lines.append(f"- {d}")
    lines += ["", f"devices compared: {len(devices)}",
              f"intended vlans: {len(intended.get('vlans', []))}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only drift detector.")
    parser.add_argument("--intended", required=True)
    parser.add_argument("--operational", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args(argv)
    try:
        intended = load_yaml(args.intended)
        operational = load_json(args.operational)
    except (OSError, ValueError) as exc:
        print(f"drift ERROR: {exc}", file=sys.stderr)
        return 1

    intended_by_name = {d["name"]: d for d in intended.get("devices", [])}
    global_vlans = {int(v["id"]): v.get("name") for v in intended.get("vlans", [])}
    drifts: list[str] = []
    for name, op in operational.get("devices", {}).items():
        if name not in intended_by_name:
            drifts.append(f"{name}: operational device unknown in intended state")
            continue
        drifts.extend(diff_device(name, intended_by_name[name], op, global_vlans))
    for name in intended_by_name:
        if name not in operational.get("devices", {}):
            drifts.append(f"{name}: intended device missing from operational snapshot")

    with open(args.report, "w", encoding="utf-8") as f:
        f.write(build_report(operational.get("devices", {}), intended, drifts))

    if drifts:
        print(f"drift FOUND: {len(drifts)} difference(s) (see {args.report})", file=sys.stderr)
        return 2 if args.fail_on_drift else 0
    print(f"drift OK: no drift (report {args.report})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
