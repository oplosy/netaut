#!/usr/bin/env python3
"""EOS running-config -> operational snapshot (T-010, INV-002).

Read-only parser: turns `show running-config` text into the side-B shape in
playbooks/drift/operational-schema.yml so the tested drift tool can serve as
the live post-check. Stdlib only. Never emits secret material: only VLANs,
explicit access ports and ntp/dns/syslog IPs are extracted.

Rules: VLAN 1 is never reported; a VLAN without a name line gets EOS's
default VLAN%04d; `vlan 10,20-21` expands; only interfaces with an explicit
`switchport access vlan N` are reported; ntp/dns/logging accept an optional
`vrf X` qualifier and keep IP tokens only.

Exit codes: 0 ok / equal, 2 --compare found differences, 1 error.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys


def _ips(tokens: list[str]) -> list[str]:
    out = []
    for tok in tokens:
        try:
            out.append(str(ipaddress.ip_address(tok)))
        except ValueError:
            continue
    return out


def _strip_vrf(tokens: list[str]) -> list[str]:
    if len(tokens) >= 2 and tokens[0] == "vrf":
        return tokens[2:]
    return tokens


def _vlan_ids(spec: str) -> list[int]:
    ids: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            ids.extend(range(int(lo), int(hi) + 1))
        elif part.isdigit():
            ids.append(int(part))
    return ids


def parse(text: str) -> dict:
    vlans: dict[int, str] = {}
    ifaces: dict[str, int] = {}
    ntp: set[str] = set()
    dns: set[str] = set()
    syslog: set[str] = set()
    block: tuple[str, object] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        tok = line.split()
        if not line.startswith(" "):
            block = None
            if tok[0] == "vlan" and len(tok) == 2:
                ids = _vlan_ids(tok[1])
                for vid in ids:
                    vlans.setdefault(vid, f"VLAN{vid:04d}")
                block = ("vlan", ids)
            elif tok[0] == "interface" and len(tok) == 2:
                block = ("interface", tok[1])
            elif tok[:2] == ["ntp", "server"]:
                ntp.update(_ips(_strip_vrf(tok[2:])[:1]))
            elif tok[:2] == ["ip", "name-server"]:
                dns.update(_ips(_strip_vrf(tok[2:])))
            elif tok[0] == "logging":
                rest = _strip_vrf(tok[1:])
                if rest[:1] == ["host"]:
                    syslog.update(_ips(rest[1:2]))
            continue
        if block and block[0] == "vlan" and tok[0] == "name" and len(tok) >= 2:
            for vid in block[1]:
                vlans[vid] = " ".join(tok[1:])
        elif block and block[0] == "interface" and tok[:3] == ["switchport", "access", "vlan"]:
            ifaces[block[1]] = int(tok[3])
    vlans.pop(1, None)
    return {
        "vlans": [{"id": v, "name": vlans[v]} for v in sorted(vlans)],
        "interfaces": [{"name": n, "access_vlan": ifaces[n]} for n in sorted(ifaces)],
        "common": {"ntp_servers": sorted(ntp), "dns_servers": sorted(dns),
                   "syslog_servers": sorted(syslog)},
    }


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EOS running-config -> snapshot.")
    parser.add_argument("--config", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--out")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = parser.parse_args(argv)
    try:
        if args.compare:
            a, b = (parse(_read(p)) for p in args.compare)
            if a == b:
                print("compare OK: snapshots equal")
                return 0
            keys = [k for k in a if a[k] != b[k]]
            print(f"compare DIFFERS: {', '.join(keys)}")
            return 2
        if not args.config or not args.out:
            parser.error("--config NAME=PATH and --out are required without --compare")
        devices = {}
        for item in args.config:
            name, _, path = item.partition("=")
            if not name or not path:
                parser.error(f"bad --config {item!r}, want NAME=PATH")
            devices[name] = parse(_read(path))
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"devices": devices, "provenance": "live running-config (eos)"},
                      f, indent=2, sort_keys=True)
    except OSError as exc:
        print(f"eos-snapshot ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"eos-snapshot OK: {len(devices)} device(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
