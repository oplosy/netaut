#!/usr/bin/env python3
"""SR Linux running datastore -> operational snapshot (T-012, INV-002).

Read-only parser: turns the JSON of `nokia.srlinux.get` on `/` (running
datastore, result[0]) into the side-B shape in
playbooks/drift/operational-schema.yml, so the tested drift tool serves as the
live post-check. Stdlib only. Never emits secret material: only VLANs,
access ports and ntp/dns/syslog IPs are extracted.

YANG module prefixes (`srl_nokia-system:system`, `srl_nokia-...:mac-vrf`)
appear inconsistently across paths and releases, so keys and identity
values are stripped of them before anything is read.

Rules: a VLAN is a network-instance named `vlan-<id>` of type mac-vrf; its
name is the description (or the instance name when unset). An access port is
an interface whose only subinterface is index 0, `bridged` with `untagged`
encapsulation, and a member of such a mac-vrf. NTP/DNS/syslog keep IP values only; DNS is the
union of every dns-instance's server-list.

--compare (restore proof) checks the parsed fields AND the whole document
(canonical JSON), so a difference anywhere fails. It prints only field names,
top-level section names and counts, never config content (hashed secrets).

Exit codes: 0 ok / equal, 2 --compare found differences, 1 error.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys

VLAN_INSTANCE = re.compile(r"^vlan-(\d+)$")


def strip_prefixes(obj):
    """Return a copy without YANG module prefixes on keys and identity values."""
    if isinstance(obj, dict):
        return {k.split(":", 1)[-1]: strip_prefixes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_prefixes(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("srl_nokia-") and ":" in obj:
        return obj.split(":", 1)[1]
    return obj


def _ips(values) -> set[str]:
    out = set()
    for value in values:
        try:
            out.add(str(ipaddress.ip_address(value)))
        except (TypeError, ValueError):
            continue
    return out


def parse(doc: dict) -> dict:
    doc = strip_prefixes(doc)
    system = doc.get("system", {})
    ntp = _ips(s.get("address") for s in system.get("ntp", {}).get("server", []))
    dns = _ips(ip for inst in system.get("dns-instance", [])
               for ip in inst.get("server-list", []))
    syslog = _ips(s.get("host") for s in system.get("logging", {}).get("remote-server", []))

    # Access-port candidates: the interface's only subinterface is .0, bridged
    # and untagged. A mixed port (extra tagged or routed subinterfaces) or an
    # untagged member on another index is not what the role configures.
    members = {}
    for iface in doc.get("interface", []):
        subs = iface.get("subinterface", [])
        if len(subs) == 1 and subs[0].get("index") == 0:
            members[f"{iface.get('name')}.0"] = (iface.get("name"), subs[0])

    vlans: dict[int, str] = {}
    ifaces: dict[str, int] = {}
    for inst in doc.get("network-instance", []):
        match = VLAN_INSTANCE.match(inst.get("name", ""))
        if not match or inst.get("type") != "mac-vrf":
            continue
        vid = int(match.group(1))
        vlans[vid] = inst.get("description", inst["name"])
        for member in inst.get("interface", []):
            parent, sub = members.get(member.get("name"), (None, None))
            encap = (sub or {}).get("vlan", {}).get("encap", {})
            if sub and sub.get("type") == "bridged" and "untagged" in encap:
                ifaces[parent] = vid
    return {
        "vlans": [{"id": v, "name": vlans[v]} for v in sorted(vlans)],
        "interfaces": [{"name": n, "access_vlan": ifaces[n]} for n in sorted(ifaces)],
        "common": {"ntp_servers": sorted(ntp), "dns_servers": sorted(dns),
                   "syslog_servers": sorted(syslog)},
    }


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: top-level object required")
    return doc


def compare(a: dict, b: dict) -> list[str]:
    pa, pb = parse(a), parse(b)
    diffs = [k for k in pa if pa[k] != pb[k]]
    # Equality on the raw documents: both come from `get /` on the same device,
    # and stripping could merge same-named keys or hide a value change. Only
    # the printed section names drop their module prefix.
    raw = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    sections = sorted({k.split(":", 1)[-1] for k in raw})
    if sections:
        diffs.append(f"config sections differ: {', '.join(sections)}")
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SR Linux running datastore -> snapshot.")
    parser.add_argument("--config", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--out")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = parser.parse_args(argv)
    try:
        if args.compare:
            diffs = compare(*(_read(p) for p in args.compare))
            if not diffs:
                print("compare OK: configs equal")
                return 0
            print(f"compare DIFFERS: {'; '.join(diffs)}")
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
            json.dump({"devices": devices, "provenance": "live running datastore (srlinux)"},
                      f, indent=2, sort_keys=True)
    except (OSError, ValueError) as exc:
        print(f"srlinux-snapshot ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"srlinux-snapshot OK: {len(devices)} device(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
