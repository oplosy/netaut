# cEOS Live Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Arista EOS as a second vendor and a free containerlab cEOS
lab. Live waves get a real pre-wave backup, a drift-based post-check,
and a verified restore.

**Architecture:** Roles keep their fail-closed asserts in `main.yml` and dispatch
module calls to `<vendor>.yml` (INV-003). Live-only safety steps (backup,
post-check, restore) live in a new `live_guard` role. It dispatches per vendor
the same way and fails closed for vendors without an implementation. The
post-check parses the device running-config into the existing
operational-snapshot shape and reuses the tested drift tool.

**Tech Stack:** Ansible core 2.21 (WSL), arista.eos, cisco.ios, containerlab,
Python 3.12 (stdlib + PyYAML + Jinja2), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-22-ceos-live-lab-design.md`

## Global Constraints

- INV-001: no credential values in the repo. The secret scan flags any
  password or secret key-value assignment, so `ansible_password` lives only in an
  encrypted vault file outside the repo (`~/.netaut/lab-vault.yml`).
- INV-003: roles contain module arguments only. No CLI strings and no Jinja
  templates in roles. Raw syntax lives in `templates/<vendor>/`.
- INV-004: missing inputs fail closed before any device step.
- Device backups and fetched configs contain the device's hashed user
  secrets. They are written outside the repo (`~/.netaut/backups`,
  `~/.netaut/runs`) and never committed. This deviates from the spec's
  `reports/backups/`; the spec is updated in Task 8.
- CI stays device-less. Every live step runs locally through `make lab-*` in WSL.
- The intended device names `lab-sw01` and `lab-sw02` are shared by `sample.yml` (ios)
  and `lab-eos.yml` (eos).

## Review Focus

1. A live wave with `netaut_wave` unset must fail before any device
   change. Otherwise backups would overwrite each other under an empty name
   (pinned in Task 6: syntax-level assert plus a device-less run with
   `netaut_mode=live` and an unreachable host that fails on the assert
   first).
2. A running-config containing default VLAN 1, unconfigured ports, `vrf`
   qualifiers on ntp/dns/logging lines, or `vlan 10,20` lists must not produce
   false drift (pinned in the Task 4 parser tests).
3. If the backup step itself fails, the rescue path must not "restore"
   from a missing file. It records that no change was made (Task 6 restore
   guard plus a parser-independent assert).
4. A vendor with no `live_guard` implementation (ios) must fail closed in
   live mode instead of silently skipping backup (Task 5 dispatch test).
5. Running render idempotency for a vendor with zero devices in the input must
   fail, not pass vacuously (Task 2 test).

---

### Task 1: Model accepts EOS; EOS intended state

**Files:**
- Modify: `netbox/schema.yml` (`platform_allowed`)
- Create: `netbox/intended/lab-eos.yml`
- Create: `scripts/tests/test_validate_model.py`

**Interfaces:**
- Produces: `netbox/intended/lab-eos.yml`, which has the same top-level shape as `sample.yml`,
  devices `lab-sw01` and `lab-sw02` with `platform: eos`, and interface `Ethernet1`.

- [ ] **Step 1: Write failing test**

```python
"""Schema validation for both vendor intended-state files (T-008)."""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VALIDATE = REPO / "scripts" / "validate_model.py"


def run(input_path):
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--schema", str(REPO / "netbox" / "schema.yml"),
         "--input", str(input_path)], capture_output=True, text=True)


def test_ios_sample_still_valid():
    assert run(REPO / "netbox" / "intended" / "sample.yml").returncode == 0


def test_eos_lab_intended_valid():
    res = run(REPO / "netbox" / "intended" / "lab-eos.yml")
    assert res.returncode == 0, res.stdout


def test_unknown_platform_rejected(tmp_path):
    text = (REPO / "netbox" / "intended" / "lab-eos.yml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yml"
    bad.write_text(text.replace("platform: eos", "platform: junos"), encoding="utf-8")
    res = run(bad)
    assert res.returncode == 1
    assert "disallowed platform" in res.stdout
```

- [ ] **Step 2: Run it.** Run `python -m pytest scripts/tests -q`. Expected: `test_eos_lab_intended_valid` FAILS (file missing).
- [ ] **Step 3: Implement.** In `netbox/schema.yml` change `platform_allowed: [ios]` to `platform_allowed: [ios, eos]`. Create `netbox/intended/lab-eos.yml` as a copy of `sample.yml` with a lab-eos header comment, each `platform: ios` changed to `platform: eos`, and each `GigabitEthernet0/0` changed to `Ethernet1`.
- [ ] **Step 4: Run it.** Run `python -m pytest scripts/tests -q`. Expected: 3 passed.
- [ ] **Step 5: Wire gates.** In `scripts/ci_gate.py` add a `validate-model-eos` step with `--input netbox/intended/lab-eos.yml`, and change pytest to `pytest roles scripts/tests -q`. In `.github/workflows/ci.yml` add a validate step for lab-eos and change pytest the same way. In `Makefile` `validate` runs both files and `test` runs `roles scripts/tests`.
- [ ] **Step 6: Commit** `feat(T-008): accept eos platform and add lab-eos intended state`

### Task 2: EOS templates and all-template render idempotency

**Files:**
- Create: `templates/eos/vlan_interface.j2`, `templates/eos/routing/static.j2`
- Modify: `scripts/render_idempotency.py` (all templates, platform filter)
- Create: `scripts/tests/test_render_idempotency.py`, `roles/vlan_interface/tests/test_render_eos.py`, `roles/routing/tests/test_routing_eos.py`
- Modify: `templates/README.md`, `ci_gate.py`, `ci.yml`, `Makefile` (render eos)

**Interfaces:**
- Consumes: `lab-eos.yml` (Task 1).
- Produces: `render_idempotency.py --input X --vendor V --repo .`. It renders
  every `templates/V/**/*.j2` for each device whose `platform == V`, with the
  context `netaut_vlans`, `netaut_interfaces`, `netaut_static_routes`,
  `netaut_prefix_lists`, `netaut_route_maps`. It exits 1 if no device matches.

- [ ] **Step 1: Write failing tests**

`roles/vlan_interface/tests/test_render_eos.py`:
```python
"""EOS VLAN/interface render (T-008): twin of the IOS render test."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "eos" / "vlan_interface.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-eos.yml"


def context():
    data = yaml.safe_load(INTENDED.read_text(encoding="utf-8"))
    device = next(d for d in data["devices"] if d["name"] == "lab-sw01")
    return {"netaut_vlans": data["vlans"], "netaut_interfaces": device["interfaces"]}


def render(ctx):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
                             undefined=jinja2.StrictUndefined, trim_blocks=True,
                             lstrip_blocks=True)
    return env.get_template(TEMPLATE.name).render(ctx)


def test_rerender_is_byte_identical():
    assert render(context()).encode() == render(context()).encode()


def test_eos_content_uses_eos_indent_and_names():
    out = render(context())
    assert "vlan 99\n   name MGMT\n" in out
    assert "interface Ethernet1\n" in out
    assert "   switchport access vlan 99\n" in out
```

`roles/routing/tests/test_routing_eos.py`:
```python
"""EOS routing render (T-008): twin of the IOS routing test."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "eos" / "routing" / "static.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-eos.yml"


def render():
    data = yaml.safe_load(INTENDED.read_text(encoding="utf-8"))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
                             undefined=jinja2.StrictUndefined, trim_blocks=True,
                             lstrip_blocks=True)
    return env.get_template(TEMPLATE.name).render(
        netaut_static_routes=data["static_routes"],
        netaut_prefix_lists=data["prefix_lists"],
        netaut_route_maps=data["route_maps"])


def test_eos_routing_content():
    out = render()
    assert "ip route 192.0.2.0/24 10.0.0.1 name LAB-WAN\n" in out
    assert "ip prefix-list PL-LAB-LOCAL seq 5 permit 10.0.0.0/24\n" in out
    assert "route-map RM-LAB-OUT permit 10\n   match ip address prefix-list PL-LAB-LOCAL\n" in out


def test_rerender_is_byte_identical():
    assert render().encode() == render().encode()
```

`scripts/tests/test_render_idempotency.py`:
```python
"""render_idempotency covers every template and refuses vacuous passes (T-008)."""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "render_idempotency.py"


def run(inp, vendor):
    return subprocess.run([sys.executable, str(TOOL), "--input", inp, "--vendor", vendor,
                           "--repo", str(REPO)], capture_output=True, text=True)


def test_ios_renders_all_templates():
    res = run("netbox/intended/sample.yml", "ios")
    assert res.returncode == 0, res.stdout
    assert "lab-sw01 vlan_interface.j2: IDENTICAL" in res.stdout
    assert "lab-sw01 routing/static.j2: IDENTICAL" in res.stdout


def test_eos_renders_all_templates():
    res = run("netbox/intended/lab-eos.yml", "eos")
    assert res.returncode == 0, res.stdout
    assert "lab-sw02 routing/static.j2: IDENTICAL" in res.stdout


def test_no_matching_platform_fails_closed():
    res = run("netbox/intended/sample.yml", "eos")
    assert res.returncode == 1
    assert "no devices with platform eos" in res.stdout
```

- [ ] **Step 2: Run it.** Run `python -m pytest scripts/tests roles/vlan_interface roles/routing -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement the templates**

`templates/eos/vlan_interface.j2`:
```jinja
{% for vlan in netaut_vlans %}
vlan {{ vlan.id }}
   name {{ vlan.name }}
{% endfor %}
{% for iface in netaut_interfaces %}
interface {{ iface.name }}
   description {{ iface.description }}
   switchport mode access
   switchport access vlan {{ iface.access_vlan }}
{% endfor %}
```

`templates/eos/routing/static.j2`:
```jinja
{% for r in netaut_static_routes %}
ip route {{ r.prefix }} {{ r.next_hop }}{% if r.name %} name {{ r.name }}{% endif %}
{% endfor %}
{% for pl in netaut_prefix_lists %}
{% for s in pl.sequences %}
ip prefix-list {{ pl.name }} seq {{ s.seq }} {{ s.action }} {{ s.prefix }}
{% endfor %}
{% endfor %}
{% for rm in netaut_route_maps %}
{% for s in rm.sequences %}
route-map {{ rm.name }} {{ s.action }} {{ s.seq }}
   match ip address prefix-list {{ s.match_prefix_list }}
{% endfor %}
{% endfor %}
```

- [ ] **Step 4: Rewrite `scripts/render_idempotency.py` `main()` body after arg parsing**

```python
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
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(vendor_dir)),
                             undefined=jinja2.StrictUndefined, trim_blocks=True,
                             lstrip_blocks=True)
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
```
The OK/FAILED tail stays unchanged. Update the module docstring: "every template under templates/<vendor>/, for devices of that platform".

- [ ] **Step 5: Run it.** Run `python -m pytest roles scripts/tests -q`. Expected: all tests pass.
- [ ] **Step 6: Wire gates.** Add a `render-idempotency-eos` step (`--input netbox/intended/lab-eos.yml --vendor eos`) to `ci_gate.py`, `ci.yml` and the Makefile `render` target. In `templates/README.md` list the `eos/` twins.
- [ ] **Step 7: Commit** `feat(T-008): eos render twins and all-template idempotency proof`

### Task 3: Vendor dispatch in roles (common, vlan_interface, routing)

**Files:**
- Modify: `roles/{common,vlan_interface,routing}/tasks/main.yml`
- Create: `roles/{common,vlan_interface,routing}/tasks/ios.yml` (moved module calls), `.../eos.yml`
- Modify: `roles/{common,vlan_interface,routing}/defaults/main.yml` (`netaut_module_state: merged`)
- Create: `scripts/tests/test_role_dispatch.py`
- Create: `playbooks/proof/rendered.yml` (device-less argspec proof)
- Modify: `requirements.yml` (add `arista.eos`)

**Interfaces:**
- Produces: `netaut_vendor` (a string, `ansible_network_os | split('.') | last`, so `ios` or `eos`).
  Every role's `main.yml` ends with
  `include_tasks: "{{ netaut_vendor }}.yml"` after asserting
  `netaut_vendor in ['ios', 'eos']`. `netaut_module_state` (default `merged`)
  feeds every module's `state:`. The proof playbook sets it to `rendered`.

- [ ] **Step 1: Write failing test** `scripts/tests/test_role_dispatch.py`

```python
"""Role vendor dispatch contract (T-008, INV-003)."""
import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ROLES = ["common", "vlan_interface", "routing"]
VENDORS = ["ios", "eos"]
MODULE = re.compile(r"^\s*(cisco\.ios|arista\.eos)\.", re.M)


def test_each_role_has_every_vendor_file():
    for role in ROLES:
        for vendor in VENDORS:
            assert (REPO / "roles" / role / "tasks" / f"{vendor}.yml").is_file(), (role, vendor)


def test_main_has_no_vendor_modules_and_dispatches():
    for role in ROLES:
        text = (REPO / "roles" / role / "tasks" / "main.yml").read_text(encoding="utf-8")
        assert not MODULE.search(text), role
        tasks = yaml.safe_load(text)
        assert tasks[-1]["ansible.builtin.include_tasks"] == "{{ netaut_vendor }}.yml", role


def test_vendor_files_only_use_their_collection():
    for role in ROLES:
        for vendor, other in (("ios", "arista.eos."), ("eos", "cisco.ios.")):
            text = (REPO / "roles" / role / "tasks" / f"{vendor}.yml").read_text(encoding="utf-8")
            assert other not in text, (role, vendor)
            assert "netaut_module_state" in text, (role, vendor)
```

- [ ] **Step 2: Run it.** Run `python -m pytest scripts/tests/test_role_dispatch.py -q`. Expected: FAIL.
- [ ] **Step 3: Split the roles.** For each role, move every module task from `main.yml` unchanged into `ios.yml`, except that `state: merged` becomes `state: "{{ netaut_module_state }}"`. Then append this to `main.yml`:

```yaml
- name: Require a supported vendor (fail closed)
  ansible.builtin.assert:
    that:
      - netaut_vendor in ['ios', 'eos']
    fail_msg: "no <role> implementation for vendor {{ netaut_vendor }}"

- name: Apply vendor module calls
  ansible.builtin.include_tasks: "{{ netaut_vendor }}.yml"
```
(Substitute the role name for `<role>`.) Add this to each `defaults/main.yml`:
```yaml
netaut_vendor: "{{ ansible_network_os | default('') | split('.') | last }}"
netaut_module_state: merged
```

`roles/common/tasks/eos.yml`:
```yaml
---
# EOS module calls for common settings (T-008). Module arguments only (INV-003).
- name: Configure NTP servers
  arista.eos.eos_ntp_global:
    config:
      servers:
        - server: "{{ item }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_common.ntp_servers }}"

- name: Configure DNS name servers
  arista.eos.eos_system:
    name_servers: "{{ netaut_common.dns_servers }}"
  when: netaut_module_state == 'merged'

- name: Configure syslog hosts
  arista.eos.eos_logging_global:
    config:
      hosts:
        - name: "{{ item }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_common.syslog_servers }}"
```
(`eos_system` has no `rendered` state, so the proof skips it. That is recorded in the report.)

`roles/vlan_interface/tasks/eos.yml`:
```yaml
---
# EOS module calls for VLANs and access ports (T-008). Module arguments only (INV-003).
- name: Ensure VLANs exist
  arista.eos.eos_vlans:
    config:
      - vlan_id: "{{ item.id }}"
        name: "{{ item.name }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_vlans }}"

- name: Ensure access interfaces
  arista.eos.eos_l2_interfaces:
    config:
      - name: "{{ item.name }}"
        mode: access
        access:
          vlan: "{{ item.access_vlan }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_interfaces }}"
```

`roles/routing/tasks/eos.yml`:
```yaml
---
# EOS module calls for static routes and policy (T-008). Module arguments only (INV-003).
- name: Ensure static routes exist
  arista.eos.eos_static_routes:
    config:
      - address_families:
          - afi: ipv4
            routes:
              - dest: "{{ item.prefix }}"
                next_hops:
                  - forward_router_address: "{{ item.next_hop }}"
                    description: "{{ item.name | default(omit) }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_static_routes }}"

- name: Ensure prefix lists exist
  arista.eos.eos_prefix_lists:
    config:
      - afi: ipv4
        prefix_lists:
          - name: "{{ item.0.name }}"
            entries:
              - action: "{{ item.1.action }}"
                address: "{{ item.1.prefix }}"
                sequence: "{{ item.1.seq }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_prefix_lists | subelements('sequences') }}"

- name: Ensure route maps exist
  arista.eos.eos_route_maps:
    config:
      - route_map: "{{ item.0.name }}"
        entries:
          - action: "{{ item.1.action }}"
            sequence: "{{ item.1.seq }}"
            match:
              ip:
                address:
                  prefix_list: "{{ item.1.match_prefix_list }}"
    state: "{{ netaut_module_state }}"
  loop: "{{ netaut_route_maps | subelements('sequences') }}"
```

- [ ] **Step 4: Run it.** Run `python -m pytest roles scripts/tests -q`. Expected: all tests pass.
- [ ] **Step 5: Device-less argspec proof** `playbooks/proof/rendered.yml`:

```yaml
---
# Device-less argspec proof (T-008): runs every role with state=rendered on
# localhost so module argument specs are validated with zero device contact.
- name: Rendered-state proof per vendor
  hosts: localhost
  gather_facts: false
  connection: local
  vars:
    netaut_module_state: rendered
    netaut_proof_vendor: eos
    netaut_intended_file: "{{ playbook_dir }}/../../netbox/intended/{{ 'lab-eos' if netaut_proof_vendor == 'eos' else 'sample' }}.yml"
    netaut_data: "{{ lookup('ansible.builtin.file', netaut_intended_file) | from_yaml }}"
    netaut_vendor: "{{ netaut_proof_vendor }}"
  tasks:
    - name: Common settings
      ansible.builtin.include_role:
        name: common
      vars:
        netaut_common: "{{ netaut_data.devices[0].common }}"
    - name: VLANs and interfaces
      ansible.builtin.include_role:
        name: vlan_interface
      vars:
        netaut_vlans: "{{ netaut_data.vlans }}"
        netaut_interfaces: "{{ netaut_data.devices[0].interfaces }}"
    - name: Routing
      ansible.builtin.include_role:
        name: routing
      vars:
        netaut_static_routes: "{{ netaut_data.static_routes }}"
        netaut_prefix_lists: "{{ netaut_data.prefix_lists }}"
        netaut_route_maps: "{{ netaut_data.route_maps }}"
```
In WSL run `ANSIBLE_ROLES_PATH=roles ansible-playbook playbooks/proof/rendered.yml -e netaut_proof_vendor=eos -v`, then the same with `-e netaut_proof_vendor=ios`. Expected: `failed=0` for both, and the `rendered` output shows the EOS lines. Add `arista.eos` (`>=10.0.0`) to `requirements.yml`, and add both proof runs to the CI `Ansible syntax checks` step (they need no device).
- [ ] **Step 6: Commit** `refactor(T-008): dispatch role module calls per vendor, add eos`

### Task 4: EOS running-config parser and single-device drift

**Files:**
- Create: `roles/live_guard/files/eos_snapshot.py`
- Create: `roles/live_guard/tests/test_eos_snapshot.py`, `roles/live_guard/tests/fixtures/{clean,drifted,vrf}.cfg`
- Modify: `roles/drift/files/drift.py` (`--device NAME`)
- Modify: `roles/drift/tests/test_idempotency.py` (device filter test)

**Interfaces:**
- Produces: `eos_snapshot.parse(text: str) -> dict` returns
  `{"vlans": [{"id": int, "name": str}], "interfaces": [{"name": str, "access_vlan": int}], "common": {"ntp_servers": [...], "dns_servers": [...], "syslog_servers": [...]}}`
  with all lists sorted.
  - CLI `eos_snapshot.py --config NAME=PATH [...] --out FILE` writes
    `{"devices": {NAME: parse(...)}, "provenance": "live running-config (eos)"}`.
  - CLI `eos_snapshot.py --compare A.cfg B.cfg` exits 0 when the snapshots are equal and
    2 when they differ, printing the differing keys.
  - `drift.py --device NAME` compares only that device.
- Parser rules: VLAN 1 is never reported. A VLAN without a `name` line gets
  `VLAN%04d`. `vlan 10,20-21` expands. Only interfaces with an explicit
  `switchport access vlan N` are reported. ntp/dns/logging accept an optional
  `vrf X` and keep only IP tokens.

- [ ] **Step 1: Fixtures.** `clean.cfg` is an EOS running-config: header `! Command: show running-config`,
  `hostname lab-sw01`, `username admin privilege 15 role network-admin secret sha512 $6$x`,
  `ntp server 10.0.0.53`, `ip name-server vrf default 10.0.0.53`, `logging host 10.0.0.54`,
  `vlan 99` plus `   name MGMT`, `interface Ethernet1` plus `   description mgmt-uplink` plus `   switchport access vlan 99`,
  `interface Ethernet2` (no body), `interface Management0` plus `   ip address 172.20.20.11/24`, and `end`, with `!` separators.
  `drifted.cfg` is the same except VLAN 99 is named `WRONG` and it has an extra `vlan 10,20-21`.
  `vrf.cfg` uses `ntp server vrf MGMT 10.0.0.53 iburst`, `logging vrf MGMT host 10.0.0.54 514`, and
  `ip name-server vrf MGMT 10.0.0.53 10.0.0.55`.
- [ ] **Step 2: Write failing tests**

```python
"""EOS running-config -> operational snapshot (T-010)."""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = REPO / "roles" / "live_guard" / "files" / "eos_snapshot.py"
sys.path.insert(0, str(TOOL.parent))
import eos_snapshot  # noqa: E402

FIX = HERE / "fixtures"


def test_clean_config_matches_intended_shape():
    snap = eos_snapshot.parse((FIX / "clean.cfg").read_text())
    assert snap == {
        "vlans": [{"id": 99, "name": "MGMT"}],
        "interfaces": [{"name": "Ethernet1", "access_vlan": 99}],
        "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],
                   "syslog_servers": ["10.0.0.54"]},
    }


def test_vlan_lists_and_default_names():
    snap = eos_snapshot.parse((FIX / "drifted.cfg").read_text())
    assert {"id": 10, "name": "VLAN0010"} in snap["vlans"]
    assert {"id": 21, "name": "VLAN0021"} in snap["vlans"]
    assert {"id": 99, "name": "WRONG"} in snap["vlans"]


def test_vrf_qualifiers_keep_only_ips():
    common = eos_snapshot.parse((FIX / "vrf.cfg").read_text())["common"]
    assert common == {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53", "10.0.0.55"],
                      "syslog_servers": ["10.0.0.54"]}


def test_cli_writes_snapshot_that_drift_accepts(tmp_path):
    out = tmp_path / "snap.json"
    res = subprocess.run([sys.executable, str(TOOL), "--config", f"lab-sw01={FIX / 'clean.cfg'}",
                          "--out", str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    drift = subprocess.run(
        [sys.executable, str(REPO / "roles" / "drift" / "files" / "drift.py"),
         "--intended", str(REPO / "netbox" / "intended" / "lab-eos.yml"),
         "--operational", str(out), "--report", str(tmp_path / "r.md"),
         "--device", "lab-sw01", "--fail-on-drift"], capture_output=True, text=True)
    assert drift.returncode == 0, drift.stderr
    assert json.loads(out.read_text())["devices"]["lab-sw01"]["vlans"][0]["id"] == 99


def test_compare_equal_and_different():
    same = subprocess.run([sys.executable, str(TOOL), "--compare", str(FIX / "clean.cfg"),
                           str(FIX / "clean.cfg")], capture_output=True, text=True)
    diff = subprocess.run([sys.executable, str(TOOL), "--compare", str(FIX / "clean.cfg"),
                           str(FIX / "drifted.cfg")], capture_output=True, text=True)
    assert same.returncode == 0
    assert diff.returncode == 2 and "vlans" in diff.stdout


def test_no_secret_material_in_snapshot():
    snap = eos_snapshot.parse((FIX / "clean.cfg").read_text())
    assert "sha512" not in json.dumps(snap)
```
Add to `roles/drift/tests/test_idempotency.py`:
```python
def test_device_filter_ignores_other_devices(tmp_path):
    """--device compares one host only: the others do not count as missing."""
    snap = tmp_path / "one.json"
    snap.write_text(
        '{"devices": {"lab-sw01": {"vlans": [{"id": 99, "name": "MGMT"}],'
        ' "interfaces": [{"name": "GigabitEthernet0/0", "access_vlan": 99}],'
        ' "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],'
        ' "syslog_servers": ["10.0.0.54"]}}}}', encoding="utf-8")
    res = run_tool(snap, tmp_path / "r.md", ("--device", "lab-sw01", "--fail-on-drift"))
    assert res.returncode == 0, res.stderr
```
- [ ] **Step 3: Run it.** Run `python -m pytest roles/live_guard roles/drift -q`. Expected: FAIL.
- [ ] **Step 4: Implement `eos_snapshot.py`**

```python
#!/usr/bin/env python3
"""EOS running-config -> operational snapshot (T-010, INV-002).

Read-only parser: turns `show running-config` text into the side-B shape in
playbooks/drift/operational-schema.yml so the tested drift tool can serve as
the live post-check. Stdlib only. Never emits secret material: only VLAN,
access-port and ntp/dns/syslog IPs are extracted.

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
        if not line.startswith(" "):
            tok = line.split()
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
        tok = line.split()
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
```
- [ ] **Step 5: Add `--device` to `drift.py`.** Add `parser.add_argument("--device", help="compare only this device")`. After building `intended_by_name`, when `args.device` is set, filter both the operational devices and `intended_by_name` to that name. If the device is not in intended, print `drift ERROR: unknown device` and return 1.
- [ ] **Step 6: Run it.** Run `python -m pytest roles scripts/tests -q`. Expected: all tests pass.
- [ ] **Step 7: Commit** `feat(T-010): eos running-config parser and single-device drift`

### Task 5: `live_guard` role (backup, post-check, restore) with vendor dispatch

**Files:**
- Create: `roles/live_guard/defaults/main.yml`, `roles/live_guard/tasks/{backup,postcheck,restore}.yml`, `roles/live_guard/tasks/eos/{backup,fetch,restore}.yml`, `roles/live_guard/README.md`
- Create: `scripts/tests/test_live_guard_contract.py`

**Interfaces:**
- Consumes: `eos_snapshot.py` and `drift.py --device` (Task 4), and `netaut_vendor` (Task 3).
- Produces: `include_role: name=live_guard tasks_from=backup|postcheck|restore`.
  - Vars: `netaut_wave` (required), `netaut_intended` (the path), `netaut_backup_dir`
    (default `{{ lookup('env','HOME') }}/.netaut/backups`), `netaut_run_dir` (default
    `{{ lookup('env','HOME') }}/.netaut/runs/{{ netaut_wave }}`).
  - `backup` sets the fact `netaut_backup_file`. `restore` is a no-op
    that says "no change was made" when `netaut_backup_file` is undefined.

- [ ] **Step 1: Write failing test**

```python
"""live_guard contract (T-011): every entry point fails closed per vendor."""
import pathlib

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
TASKS = REPO / "roles" / "live_guard" / "tasks"


def test_entry_points_assert_vendor_and_wave_before_anything():
    for entry in ("backup", "postcheck", "restore"):
        tasks = yaml.safe_load((TASKS / f"{entry}.yml").read_text(encoding="utf-8"))
        first = tasks[0]["ansible.builtin.assert"]["that"]
        assert "netaut_vendor in ['eos']" in first, entry
        assert "netaut_wave | default('') | length > 0" in first, entry


def test_ios_has_no_live_implementation_yet():
    assert not (TASKS / "ios").exists()


def test_backup_and_fetch_write_outside_repo():
    defaults = (REPO / "roles" / "live_guard" / "defaults" / "main.yml").read_text(encoding="utf-8")
    assert "~/.netaut" in defaults or "env','HOME'" in defaults
    assert "reports/" not in defaults


def test_restore_is_guarded_by_backup_presence():
    text = (TASKS / "restore.yml").read_text(encoding="utf-8")
    assert "netaut_backup_file is defined" in text
```
- [ ] **Step 2: Run it.** Run `python -m pytest scripts/tests/test_live_guard_contract.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**

`roles/live_guard/defaults/main.yml`:
```yaml
---
# Live-wave guard defaults (T-010/T-011). Backups and fetched configs hold the
# device's hashed user secrets, so they live outside the repo (INV-001).
netaut_wave: ""
netaut_backup_dir: "{{ lookup('env','HOME') }}/.netaut/backups"
netaut_run_dir: "{{ lookup('env','HOME') }}/.netaut/runs/{{ netaut_wave }}"
netaut_vendor: "{{ ansible_network_os | default('') | split('.') | last }}"
live_guard_files: "{{ role_path }}/files"
live_guard_drift: "{{ role_path }}/../drift/files/drift.py"
```

The shared first task, prepended identically to each entry point:
```yaml
- name: Require supported vendor and wave id (fail closed)
  ansible.builtin.assert:
    that:
      - netaut_vendor in ['eos']
      - netaut_wave | default('') | length > 0
    fail_msg: "live_guard: vendor {{ netaut_vendor }} has no live implementation or netaut_wave unset"
```

`tasks/backup.yml` = the assert, then:
```yaml
- name: Ensure local backup and run directories
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    mode: "0700"
  loop: ["{{ netaut_backup_dir }}", "{{ netaut_run_dir }}"]
  delegate_to: localhost
  changed_when: false

- name: Take pre-wave backup
  ansible.builtin.include_tasks: "{{ netaut_vendor }}/backup.yml"

- name: Backup must exist and be non-empty (fail closed)
  ansible.builtin.stat:
    path: "{{ netaut_backup_dir }}/{{ inventory_hostname }}-{{ netaut_wave }}.cfg"
  delegate_to: localhost
  register: live_guard_backup_stat

- name: Assert backup present
  ansible.builtin.assert:
    that:
      - live_guard_backup_stat.stat.exists
      - live_guard_backup_stat.stat.size > 0
    fail_msg: "pre-wave backup missing for {{ inventory_hostname }}; wave not started"

- name: Record backup path for restore
  ansible.builtin.set_fact:
    netaut_backup_file: "{{ live_guard_backup_stat.stat.path }}"
```

`tasks/eos/backup.yml`:
```yaml
---
- name: Save running-config (arista.eos backup, no device change)
  arista.eos.eos_config:
    backup: true
    backup_options:
      dir_path: "{{ netaut_backup_dir }}"
      filename: "{{ inventory_hostname }}-{{ netaut_wave }}.cfg"
  changed_when: false
```

`tasks/eos/fetch.yml` (input `live_guard_fetch_to`):
```yaml
---
- name: Read running-config
  arista.eos.eos_command:
    commands: ["show running-config"]
  register: live_guard_running

- name: Store fetched running-config locally
  ansible.builtin.copy:
    content: "{{ live_guard_running.stdout[0] }}\n"
    dest: "{{ live_guard_fetch_to }}"
    mode: "0600"
  delegate_to: localhost
  changed_when: false
```

`tasks/postcheck.yml` = the assert, then:
```yaml
- name: Fetch post-wave running-config
  ansible.builtin.include_tasks: "{{ netaut_vendor }}/fetch.yml"
  vars:
    live_guard_fetch_to: "{{ netaut_run_dir }}/{{ inventory_hostname }}-post.cfg"

- name: Build operational snapshot from running-config
  ansible.builtin.command:
    argv: [python3, "{{ live_guard_files }}/{{ netaut_vendor }}_snapshot.py",
           --config, "{{ inventory_hostname }}={{ netaut_run_dir }}/{{ inventory_hostname }}-post.cfg",
           --out, "{{ netaut_run_dir }}/{{ inventory_hostname }}-post.json"]
  delegate_to: localhost
  changed_when: false

- name: Post-check = drift against intended (rc 0 only)
  ansible.builtin.command:
    argv: [python3, "{{ live_guard_drift }}", --intended, "{{ netaut_intended }}",
           --operational, "{{ netaut_run_dir }}/{{ inventory_hostname }}-post.json",
           --report, "{{ netaut_run_dir }}/{{ inventory_hostname }}-drift.md",
           --device, "{{ inventory_hostname }}", --fail-on-drift]
  delegate_to: localhost
  changed_when: false
```

`tasks/restore.yml` = the assert, then:
```yaml
- name: Nothing to restore when the backup never happened
  ansible.builtin.debug:
    msg: "no backup for {{ inventory_hostname }}: wave failed before any change"
  when: netaut_backup_file is not defined

- name: Restore and verify
  when: netaut_backup_file is defined
  block:
    - name: Replace running-config with pre-wave backup
      ansible.builtin.include_tasks: "{{ netaut_vendor }}/restore.yml"

    - name: Fetch restored running-config
      ansible.builtin.include_tasks: "{{ netaut_vendor }}/fetch.yml"
      vars:
        live_guard_fetch_to: "{{ netaut_run_dir }}/{{ inventory_hostname }}-restored.cfg"

    - name: Restored state must equal backup
      ansible.builtin.command:
        argv: [python3, "{{ live_guard_files }}/{{ netaut_vendor }}_snapshot.py", --compare,
               "{{ netaut_backup_file }}", "{{ netaut_run_dir }}/{{ inventory_hostname }}-restored.cfg"]
      delegate_to: localhost
      changed_when: false

    - name: Restore verified marker
      ansible.builtin.debug:
        msg: "restore verified for {{ inventory_hostname }} from {{ netaut_backup_file }}"
```

`tasks/eos/restore.yml`:
```yaml
---
- name: Replace running-config with backup (config session)
  arista.eos.eos_config:
    src: "{{ netaut_backup_file }}"
    replace: config
```
The snapshot tool is resolved as `<vendor>_snapshot.py` (Task 4 created `eos_snapshot.py`). README: purpose, entry points, fail-closed rules, and why the files live outside the repo.
- [ ] **Step 4: Run it.** Run `python -m pytest roles scripts/tests -q` and yamllint. Expected: all pass.
- [ ] **Step 5: Commit** `feat(T-011): live_guard role with backup, post-check and verified restore`

### Task 6: Deploy wave uses `live_guard`

**Files:**
- Modify: `playbooks/deploy/site.yml`, `playbooks/deploy/rollback.yml`

**Interfaces:**
- Consumes: `live_guard` (Task 5) and `netaut_intended_file` (inventory var, Task 7).

- [ ] **Step 1: Edit `site.yml`.**
  - Set `hosts: lab`.
  - Set `netaut_intended: "{{ netaut_intended_file | default(playbook_dir ~ '/../../netbox/intended/sample.yml') }}"`.
  - Add `netaut_wave: ""` with the comment "set per wave record (-e netaut_wave=W-...)".
  - Inside the block, first add a task `include_role: {name: live_guard, tasks_from: backup}` with `when: netaut_mode == 'live'`.
  - Change the post-check into two tasks. First, `include_role: {name: live_guard, tasks_from: postcheck}` with `when: netaut_mode == 'live'`. Second, keep the existing drill assert.
- [ ] **Step 2: Edit `rollback.yml`.** Keep the marker task. Replace the fail-closed assert with `include_role: {name: live_guard, tasks_from: restore}` with `when: netaut_mode == 'live'`. The restore entry point fails closed for ios and when no wave is set. Update the header comment.
- [ ] **Step 3: Verify device-less (WSL).**
  - Run `ANSIBLE_ROLES_PATH=roles ansible-playbook playbooks/deploy/site.yml -i inventories/lab.yml --syntax-check`.
  - Run the same with `-i inventories/lab-eos.yml`.
  - Run `--check --diff` with both inventories.
  - Run the drill `-e netaut_force_postcheck_fail=true` with lab.yml. Expected: FAILED after the rollback marker, as before.
  - Review Focus 1: run `-i inventories/lab-eos.yml -e netaut_mode=live -e netaut_wave=` with the lab down. Expected: it fails on the live_guard assert "netaut_wave unset" before any connection attempt, because the assert runs locally.
- [ ] **Step 4: Commit** `feat(T-010): wire live_guard backup, drift post-check and restore into the wave`

### Task 7: Lab bring-up files and `make lab-*`

**Files:**
- Create: `lab/netaut.clab.yml`, `lab/README.md`, `inventories/lab-eos.yml`, `scripts/lab_verify.py`, `scripts/tests/test_lab_verify.py`
- Modify: `Makefile`, `.gitignore` (`clab-*/`), `.github/workflows/ci.yml` (eos syntax check plus dry run)

**Interfaces:**
- Produces:
  - `make lab-up`, `lab-down`, `lab-vault` and `lab-verify`, all of which run inside WSL.
  - `scripts/lab_verify.py --inventory inventories/lab-eos.yml --wave W`. It runs the live checks from the spec in order and prints one PASS/FAIL line per check.
  - `lab_verify.changed_counts(recap: str) -> dict[str, int]`.

- [ ] **Step 1: Topology** `lab/netaut.clab.yml`:
```yaml
# Free live lab (T-009, ADR-006). Image is imported locally by the OWNER and
# never committed: docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>.
name: netaut
mgmt:
  network: netaut-mgmt
  ipv4-subnet: 172.20.20.0/24
topology:
  kinds:
    arista_ceos:
      image: ${CEOS_IMAGE:=ceos:latest}
  nodes:
    lab-sw01:
      kind: arista_ceos
      mgmt-ipv4: 172.20.20.11
    lab-sw02:
      kind: arista_ceos
      mgmt-ipv4: 172.20.20.12
  links:
    - endpoints: ["lab-sw01:eth1", "lab-sw02:eth1"]
```
- [ ] **Step 2: Inventory** `inventories/lab-eos.yml`:
```yaml
# cEOS lab inventory (T-009). Connection details only; ansible_password comes
# from the encrypted ~/.netaut/lab-vault.yml at runtime (INV-001).
all:
  children:
    lab:
      children:
        eos:
          hosts:
            lab-sw01:
              ansible_host: 172.20.20.11
            lab-sw02:
              ansible_host: 172.20.20.12
          vars:
            ansible_network_os: arista.eos.eos
            ansible_connection: ansible.netcommon.network_cli
            ansible_become: true
            ansible_become_method: enable
            netaut_intended_file: "{{ inventory_dir }}/../netbox/intended/lab-eos.yml"
      vars:
        ansible_user: "{{ vault_lab_user | default('admin') }}"
```
- [ ] **Step 3: Failing test** `scripts/tests/test_lab_verify.py`:
```python
"""lab_verify recap parsing (T-010): rerun idempotency is judged from the recap."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lab_verify  # noqa: E402

RECAP = """PLAY RECAP *********************************************************************
lab-sw01                   : ok=12   changed=0    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
lab-sw02                   : ok=12   changed=3    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
localhost                  : ok=1    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
"""


def test_changed_counts_per_host():
    assert lab_verify.changed_counts(RECAP) == {"lab-sw01": 0, "lab-sw02": 3, "localhost": 0}


def test_empty_recap_is_error():
    assert lab_verify.changed_counts("no recap here") == {}
```
- [ ] **Step 4: Implement `scripts/lab_verify.py`**
```python
#!/usr/bin/env python3
"""Live lab verification (T-010/T-011). Runs inside WSL against a running lab.

Checks, in order (spec success criteria). The drill runs FIRST on a pristine
lab so the backup differs from the wave's changes; restore then proves a real
undo, not a no-op:
  1 drill       forced post-check failure exits non-zero AND every host logs
                "restore verified" (restored state == pristine backup)
  2 deploy      live wave exits 0 (post-check = drift rc 0 per host)
  3 rerun       second live wave exits 0 with changed=0 on every lab host
Exit 0 only when all checks pass. Output is the evidence for reports/.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

RECAP = re.compile(r"^(\S+)\s+:\s+ok=\d+\s+changed=(\d+)", re.M)
HOSTS = ("lab-sw01", "lab-sw02")


def changed_counts(recap: str) -> dict[str, int]:
    return {host: int(n) for host, n in RECAP.findall(recap)}


def play(inventory: str, wave: str, extra: list[str]) -> subprocess.CompletedProcess:
    cmd = ["ansible-playbook", "playbooks/deploy/site.yml", "-i", inventory,
           "-e", "netaut_mode=live", "-e", f"netaut_wave={wave}", *extra]
    env = dict(os.environ, ANSIBLE_ROLES_PATH="roles")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live waves against the lab.")
    parser.add_argument("--inventory", default="inventories/lab-eos.yml")
    parser.add_argument("--wave", required=True)
    parser.add_argument("--vault-args", default="", help="extra args, e.g. -e @vault --vault-password-file f")
    args = parser.parse_args(argv)
    extra = args.vault_args.split()
    results: list[tuple[str, bool, str]] = []

    drill = play(args.inventory, f"{args.wave}-a", extra + ["-e", "netaut_force_postcheck_fail=true"])
    restored = all(f"restore verified for {h}" in drill.stdout for h in HOSTS)
    results.append(("drill", drill.returncode != 0 and restored,
                    f"rc={drill.returncode} restore_verified={restored}"))

    first = play(args.inventory, f"{args.wave}-b", extra)
    results.append(("deploy", first.returncode == 0, f"rc={first.returncode}"))

    second = play(args.inventory, f"{args.wave}-c", extra)
    counts = changed_counts(second.stdout)
    idem = second.returncode == 0 and all(counts.get(h) == 0 for h in HOSTS)
    results.append(("rerun", idem, f"rc={second.returncode} changed={counts}"))

    for name, ok, detail in results:
        print(f"{name}: {'PASS' if ok else 'FAIL'} ({detail})")
    if not all(ok for _, ok, _ in results):
        for proc in (drill, first, second):
            print(proc.stdout[-4000:])
        return 1
    print("lab-verify OK: all live checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
- [ ] **Step 5: Makefile targets** (commands run inside WSL from the repo root):
```make
CEOS_IMAGE ?= ceos:latest
LAB_VAULT ?= $(HOME)/.netaut/lab-vault.yml
LAB_VAULT_PASS ?= $(HOME)/.netaut/vault_pass
WAVE ?= W-$(shell date +%Y%m%d-%H%M%S)

lab-up:
	CEOS_IMAGE=$(CEOS_IMAGE) sudo -E containerlab deploy -t lab/netaut.clab.yml --reconfigure

lab-down:
	sudo containerlab destroy -t lab/netaut.clab.yml --cleanup

lab-vault:
	scripts/lab_vault.sh $(LAB_VAULT) $(LAB_VAULT_PASS)

lab-verify:
	python3 scripts/lab_verify.py --inventory inventories/lab-eos.yml --wave $(WAVE) \
	  --vault-args "-e @$(LAB_VAULT) --vault-password-file $(LAB_VAULT_PASS)"
```
Create `scripts/lab_vault.sh`. If the vault file already exists it does nothing. Otherwise it creates `~/.netaut` (mode 700), writes a random vault password file (mode 600, `openssl rand -hex 32`), and writes `vault_lab_user: admin` plus the ansible password line for the containerlab cEOS default login into a temp file. It encrypts that file with `ansible-vault encrypt --vault-password-file` into `$LAB_VAULT` and deletes the plaintext. Everything is written outside the repo and nothing is echoed. Add `clab-*/` to `.gitignore`.
- [ ] **Step 6: CI.** Add `arista.eos` (already added in Task 3 through requirements.yml). Add `--syntax-check` and `--check --diff` of `site.yml` with `-i inventories/lab-eos.yml`.
- [ ] **Step 7: Run it.** Run `python -m pytest roles scripts/tests -q`, then `make gates`, then the WSL syntax checks. Expected: all pass.
- [ ] **Step 8: Commit** `feat(T-009): containerlab ceos topology, eos inventory and make lab targets`

### Task 8: Orchestration records, docs, evidence

**Files:**
- Create: `docs/orchestration/change-requests/ACR-005.md`, `docs/decisions/ADR-006.md`, `docs/orchestration/tasks/T-008.yaml` … `T-011.yaml`, `reports/T-008.txt`, `reports/reviews/T-011.md`
- Modify: `docs/decisions/ADR-005.md` (accepted), `ADR-004.md` (superseded note), `docs/orchestration/state.yaml`, `docs/registry.yaml` (REQ-009 live lab waves), spec (backup path), `README.md`, `CHANGELOG.md`, `docs/runbook.md` (lab section)

- [ ] **Step 1:** Write ACR-005 in the ACR-003 format: Context, Decision, Impact, Rollback. It supersedes ACR-003 decision 1 only.
- [ ] **Step 2:** Write ADR-006 in the ADR-004 format and set ADR-005 to `accepted (ACR-005)`. In ADR-005, note the deviation: backups are stored under `~/.netaut/backups`, not `reports/backups`, because of INV-001.
- [ ] **Step 3:** Write the task YAMLs in the T-007 format. T-008 is MODERATE, T-009 LOW, T-010 HIGH, and T-011 HIGH with `review_required: true`. In `state.yaml`: T-008 DONE (evidence reports/T-008.txt), T-009/T-010/T-011 `BLOCKED` with `blocked_on: OWNER cEOS image + Docker Desktop` until the live run.
- [ ] **Step 4:** Write `reports/T-008.txt`: files, verification output (pytest count, render ios/eos, rendered-state proofs), and invariants.
- [ ] **Step 5:** Get a fresh-context review of the T-010/T-011 code (live_guard, site.yml, rollback.yml) and write it to `reports/reviews/T-011.md`.
- [ ] **Step 6:** Update the README (vendors, lab quickstart, honest status: live checks pending the image), the CHANGELOG, and a runbook lab section. Then run `make gates`.
- [ ] **Step 7: Commit** `docs: record ACR-005, ADR-006, T-008..T-011 state and evidence`

### Task 9 (BLOCKED on OWNER prerequisites): live run and evidence

- [ ] Start from a pristine lab (`make lab-down lab-up`): the drill must run before any wave.
- [ ] `docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>`, `make lab-up CEOS_IMAGE=ceos:<ver>`, `make lab-vault`, `make lab-verify`
- [ ] Commit the output to `reports/T-009.txt`, `T-010.txt` and `T-011.txt`, move the tasks to DONE in `state.yaml`, and update the README proof list.
