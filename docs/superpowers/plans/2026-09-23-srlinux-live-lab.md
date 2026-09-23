# SR Linux Live Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run netaut's first real live waves (apply, post-check, rerun `changed=0`, forced failure with verified restore) on a free 2-node Nokia SR Linux containerlab lab, while keeping EOS and IOS untouched.

**Architecture:** SR Linux becomes a third vendor key `srlinux` in the existing per-role dispatch (`roles/<role>/tasks/srlinux.yml`, `roles/live_guard/tasks/srlinux/`). Ansible drives it with the `nokia.srlinux` collection over JSON-RPC (httpapi). Backup, post-check and restore proof all read the whole running datastore (`/`) as JSON. A stdlib parser turns that JSON into the drift tool's operational shape. `site.yml` and the drift tool do not change.

**Tech Stack:** Ansible core 2.21, `nokia.srlinux` 1.1.1, `ansible.netcommon`, `community.general` (`dict_kv`), containerlab 0.77+ in WSL Ubuntu, SR Linux `ghcr.io/nokia/srlinux:26.7.2`, Python 3.12 stdlib + PyYAML + pytest, Jinja2.

**Spec:** `docs/superpowers/specs/2026-09-23-srlinux-live-lab-design.md` (Task 1 appends the planning amendments listed below).

## Spike findings this plan relies on (2026-09-23, throwaway, SR Linux 26.7.2)

Proven on a real node through raw JSON-RPC and through `nokia.srlinux` 1.1.1:
- `nokia.srlinux.config` first apply `changed=True`, identical second apply `changed=False`.
- `nokia.srlinux.config` `replace` of path `/` with the value returned by `nokia.srlinux.get` of `/` (datastore `running`) returns the device to a byte-equal running datastore after a real change. **Root replace works; the narrow-path fallback in the spec is not needed.**
- DNS lives at `/system/dns-instance[name=...]` (there is no `/system/dns` on 26.7). Containerlab creates `dns-instance clab-default` (network-instance `mgmt`, `server-list [10.255.255.254]`). `replace` on `.../server-list` swaps the list cleanly.
- An `untagged` encap on a bridged subinterface is rejected unless the parent interface has `vlan-tagging: true`.
- JSON keys and identity values carry YANG module prefixes inconsistently (`srl_nokia-system:system`, `srl_nokia-network-instance:mac-vrf`, but `/system/logging` returns bare keys). The parser strips prefixes everywhere.
- The running datastore contains the admin user's hashed password. Backups and fetched files are secret material.
- Containerlab must keep its lab directory on the Linux filesystem: with the lab dir under `/mnt/c`, SR Linux's startup commit fails ("Setting permissions ... Operation not permitted") and JSON-RPC never opens. `CLAB_LABDIR_BASE=$HOME/.netaut/clab` fixes it.
- WSL stops the VM (and every container) when the last `wsl.exe` session ends. Lab up, verify and down must run in one WSL session (`make lab-cycle`).
- JSON-RPC answered about 5 s after `containerlab deploy` returned.

## Global Constraints

- Vendor key is `srlinux` everywhere (platform value, task file names, template dir, snapshot script). It comes from `ansible_network_os: nokia.srlinux.srlinux` via the existing `split('.') | last` rule.
- SR Linux image: `ghcr.io/nokia/srlinux:26.7.2`. Collection: `nokia.srlinux` `1.1.1` (exact pin).
- Lab mgmt network `172.20.21.0/24`, nodes `lab-sw01` = `.11`, `lab-sw02` = `.12`, link `ethernet-1/1` <-> `ethernet-1/1`.
- VLAN `N` = network-instance `vlan-N`, `type mac-vrf`, `description` = VLAN name. Access port = interface with `vlan-tagging: true`, `subinterface 0` `type bridged` with `vlan encap untagged`, `<if>.0` attached to `vlan-N`.
- Every `nokia.srlinux.config` call sets `save_when: never`.
- Backups/fetches live under `~/.netaut` with mode `0600`, never in the repo, never printed (INV-001). Tasks that carry them use `no_log: true`.
- INV-003: role `main.yml` files keep only asserts and the dispatch include; module calls live in `tasks/<vendor>.yml`.
- CI stays device-less. Live checks run locally; their output is committed under `reports/`.
- Routing stays render-only and has no `srlinux` implementation; the routing role keeps failing closed for `srlinux`.
- Commits: conventional subjects, ≤ 72 chars, end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work on branch `feat/srlinux-live-lab`.

## Review Focus

1. A backup whose content contains Jinja braces (`{{ ... }}` in a description or banner) must be restored verbatim, not rendered. Test: Task 6 Step 1 (`test_srlinux_restore_value_is_not_templated`).
2. A future SR Linux release that returns bare (unprefixed) keys, or prefixes a key we read bare today, must parse identically. Test: Task 4 Step 1 (`test_prefix_free_document_parses_the_same`).
3. The lab is up but JSON-RPC is not yet (or never) answering: `lab-verify` must fail fast before any wave and say which host. Test: Task 7 Step 1 (`test_main_fails_before_any_play_when_a_host_is_not_ready`).
4. Restore comparison and snapshot output must never print config content (hashed admin password). Test: Task 4 Step 1 (`test_compare_output_never_contains_config_content`) and Task 6 Step 1 (`test_srlinux_secret_tasks_are_no_log`).
5. An intended access port that exists on the device but is tagged, or not bridged, must show up as drift, not as a match. Test: Task 4 Step 1 (`test_tagged_subinterface_is_not_an_access_port`).

Known, accepted gap (recorded in ADR-007, not tested): moving an existing access port to a different VLAN makes the wave's commit fail (the subinterface would sit in two mac-vrfs), so the wave goes to rescue and restores. It never leaves a half state; supporting moves is a later task.

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `docs/orchestration/change-requests/ACR-006.md` | Scope decision: live lab on SR Linux, cEOS optional | 1 |
| `docs/decisions/ADR-007.md` | SR Linux lab decision, lab-only cert exception, known gap | 1 |
| `docs/decisions/ADR-006.md` | Note pointing to ADR-007 | 1 |
| `docs/registry.yaml` | REQ-009 text generalised | 1 |
| `docs/orchestration/state.yaml`, `tasks/T-012..T-015.yaml`, `tasks/T-009..T-011.yaml` | Task records | 1 |
| `docs/superpowers/specs/2026-09-23-srlinux-live-lab-design.md` | Planning amendments | 1 |
| `netbox/schema.yml` | `platform_allowed` gains `srlinux` | 2 |
| `netbox/intended/lab-srlinux.yml` | SR Linux lab intended state | 2 |
| `scripts/tests/test_validate_model.py` | srlinux intended valid | 2 |
| `templates/srlinux/vlan_interface.j2` | Flat `set /` preview render | 3 |
| `roles/vlan_interface/tests/test_render_srlinux.py` | Render test | 3 |
| `roles/live_guard/files/srlinux_snapshot.py` | JSON -> operational snapshot, `--compare` | 4 |
| `roles/live_guard/tests/fixtures/srlinux/*.json` | Captured-shape fixtures (no secrets) | 4 |
| `roles/live_guard/tests/test_srlinux_snapshot.py` | Parser tests | 4 |
| `roles/common/tasks/srlinux.yml`, `roles/vlan_interface/tasks/srlinux.yml` | Module calls | 5 |
| `roles/common/defaults/main.yml` | `netaut_srlinux_mgmt_instance`, `netaut_srlinux_dns_instance` | 5 |
| `roles/common/tasks/main.yml`, `roles/vlan_interface/tasks/main.yml` | Vendor assert gains `srlinux` | 5 |
| `scripts/tests/test_role_dispatch.py` | Dispatch contract for srlinux | 5 |
| `requirements.yml` | `nokia.srlinux` 1.1.1 | 5 |
| `roles/live_guard/tasks/srlinux/{backup,fetch,restore}.yml` | Vendor live actions | 6 |
| `roles/live_guard/defaults/main.yml` | `live_guard_ext` per vendor | 6 |
| `roles/live_guard/tasks/{backup,postcheck,restore}.yml`, `tasks/eos/backup.yml` | Vendor assert + extension | 6 |
| `scripts/tests/test_live_guard_contract.py` | Contract for srlinux | 6 |
| `lab/netaut-srlinux.clab.yml` | Topology | 7 |
| `inventories/lab-srlinux.yml` | Inventory | 7 |
| `scripts/lab_vault.sh` | Login as 3rd argument | 7 |
| `scripts/lab_verify.py`, `scripts/tests/test_lab_verify.py` | Readiness wait, image line | 7 |
| `Makefile`, `.github/workflows/ci.yml` | `LAB` switch, `lab-cycle`, CI steps | 2, 3, 7 |
| `reports/T-012.txt..T-015.txt`, `reports/reviews/T-015.md`, `README.md`, `docs/runbook.md`, `CHANGELOG.md` | Evidence and docs | 8 |

---

### Task 1: Decision records and spec amendments

**Files:**
- Create: `docs/orchestration/change-requests/ACR-006.md`, `docs/decisions/ADR-007.md`, `docs/orchestration/tasks/T-012.yaml`, `T-013.yaml`, `T-014.yaml`, `T-015.yaml`
- Modify: `docs/decisions/ADR-006.md`, `docs/registry.yaml:52-56`, `docs/orchestration/state.yaml`, `docs/orchestration/tasks/T-009.yaml`, `T-010.yaml`, `T-011.yaml`, `docs/superpowers/specs/2026-09-23-srlinux-live-lab-design.md`

**Interfaces:**
- Consumes: nothing.
- Produces: task ids T-012..T-015 used in comments and reports by every later task.

- [ ] **Step 1: Write ACR-006**

```markdown
# ACR-006 — Move the live lab to free Nokia SR Linux

Status: accepted. Baseline: v1 (scope extension).
Date: 2026-09-23. Raised by: ORCHESTRATOR, decided by: OWNER (in chat).

## Context
ACR-005 put live execution on cEOS, but Arista registration rejects personal
e-mail and the OWNER has no corporate address, so T-009..T-011 cannot run.
Unofficial cEOS images are rejected (licence, untrusted source). Nokia SR
Linux is published at ghcr.io/nokia/srlinux with no account.

## Decision
1. SR Linux is the default live lab (ADR-007). cEOS stays supported and
   optional: T-009..T-011 stay BLOCKED on an OWNER corporate Arista account.
2. SR Linux is a third vendor, key `srlinux`, through the existing per-role
   dispatch (INV-003 unchanged). EOS and IOS code is not changed.
3. New tasks: T-012 (model, render, dispatch, parser), T-013 (lab bring-up),
   T-014 (live wave + post-check), T-015 (backup/restore, HIGH, reviewed).
4. CI stays device-less for live checks even though the image is public
   (OWNER decision, 2026-09-23). ACR-003's no-pay rule stays.

## Impact
REQ-009 is generalised to "a free lab". Routing has no srlinux
implementation and stays render-only.

## Rollback
Revert the T-012..T-015 commits; ACR-005 then applies unchanged.
```

- [ ] **Step 2: Write ADR-007**

```markdown
# ADR-007 — Containerlab + Nokia SR Linux lab (default live lab)

Status: accepted (ACR-006). ADR-006 stays accepted for EOS but is no longer the default.

## Context
Live waves need a reversible blast radius (ASM-001, OPS-001) at zero cost
(ACR-003). cEOS needs a corporate Arista account the OWNER does not have.

## Decision
Containerlab with 2x SR Linux 26.7.2 (`lab/netaut-srlinux.clab.yml`, mgmt
172.20.21.0/24), run from WSL with the lab directory on the Linux filesystem.
Ansible uses `nokia.srlinux` 1.1.1 over JSON-RPC (httpapi). Backup and
restore are whole running-datastore JSON (`get /`, `replace /`), proven
byte-equal on 26.7.2 during planning. Login comes from an encrypted vault
under ~/.netaut (INV-001).

Lab-only exception: `ansible_httpapi_validate_certs: false`, because
containerlab issues a self-signed certificate per lab. Never copy this to a
non-lab inventory.

## Alternatives rejected
- network_cli with raw CLI: no cliconf plugin, hand-written idempotency.
- gNMI via gnmic + command: leaves Ansible, hand-written `changed`.
- Removing EOS: throws away tested code.

## Consequences
SR Linux's config model differs from IOS/EOS (VLAN = mac-vrf `vlan-N`,
access port = bridged untagged subinterface), so it has its own role files
and snapshot parser. No device-less argspec proof exists for
`nokia.srlinux.config` (no `rendered` state); the live lab proves it.
Known gap: moving an access port to another VLAN fails the commit and the
wave restores; supporting moves is a later task.
```

- [ ] **Step 3: Add the note to ADR-006**

In `docs/decisions/ADR-006.md` replace the line

```markdown
- Nokia SR Linux: free, but its config model is unlike IOS, so the render layer would need a rewrite.
```

with

```markdown
- Nokia SR Linux: free, but its config model is unlike IOS, so the render layer would need a rewrite.
  (2026-09-23: accepted after all as the default lab in ADR-007, because cEOS
  needs a corporate Arista account the OWNER does not have.)
```

and change the status line to `Status: accepted (ACR-005). Replaces ADR-004. Default lab moved to ADR-007 (ACR-006).`

- [ ] **Step 4: Generalise REQ-009 in `docs/registry.yaml`**

Replace the REQ-009 `text` and `source` lines with:

```yaml
    text: Live waves on a free lab (SR Linux default, cEOS optional) take a pre-wave backup, pass a device-state post-check and restore verifiably on failure.
    level: MUST
    status: ACTIVE
    source: owner decisions in chat 2026-09-22 (ACR-005) and 2026-09-23 (ACR-006)
```

- [ ] **Step 5: Task files T-012..T-015**

`docs/orchestration/tasks/T-012.yaml`:

```yaml
id: T-012
title: SR Linux model, render, role dispatch and snapshot parser
implements: [REQ-009]
preserves: [INV-001, INV-002, INV-003, INV-004]
addresses: [OPS-002]
baseline: v1
depends_on: [T-008]
owns:
  - netbox/
  - templates/srlinux/
  - roles/common/
  - roles/vlan_interface/
  - roles/live_guard/files/srlinux_snapshot.py
  - roles/live_guard/tests/
  - requirements.yml
must_not_touch:
  - templates/ios/
  - templates/eos/
shared_owner: false
risk: MEDIUM
review_required: false
objective: >
  srlinux is a valid platform with a render twin, role module calls and a
  JSON snapshot parser, all proven device-less in CI.
acceptance:
  - id: A1
    text: Model, render idempotency and all pytest suites pass with srlinux included.
    verified_by: V1
verify:
  - id: V1
    cmd: make gates
    expect: exit 0
out_of_scope:
  - srlinux routing (render-only, fails closed)
```

`docs/orchestration/tasks/T-013.yaml`:

```yaml
id: T-013
title: Containerlab SR Linux lab bring-up
implements: [REQ-009]
preserves: [INV-001]
addresses: [OPS-001]
baseline: v1
depends_on: [T-012]
owns:
  - lab/netaut-srlinux.clab.yml
  - inventories/lab-srlinux.yml
  - scripts/lab_vault.sh
  - scripts/lab_verify.py
  - Makefile
must_not_touch:
  - roles/
  - templates/
shared_owner: false
risk: LOW
review_required: false
objective: >
  Two SR Linux nodes answer JSON-RPC with a vault-held login, brought up and
  torn down by make targets from one WSL session.
acceptance:
  - id: A1
    text: make lab-up LAB=srlinux yields two running nodes answering on 172.20.21.11/.12:443.
    verified_by: V1
verify:
  - id: V1
    cmd: make lab-up LAB=srlinux && containerlab inspect -t lab/netaut-srlinux.clab.yml
    expect: two nodes running
out_of_scope:
  - Running the lab in CI (OWNER decision 2026-09-23)
```

`docs/orchestration/tasks/T-014.yaml`:

```yaml
id: T-014
title: Live SR Linux wave with real post-check
implements: [REQ-004, REQ-009]
preserves: [INV-001, INV-002]
addresses: [OPS-001]
baseline: v1
depends_on: [T-013]
owns:
  - roles/live_guard/tasks/srlinux/fetch.yml
  - roles/live_guard/tasks/postcheck.yml
must_not_touch:
  - templates/
  - netbox/
shared_owner: true
risk: MEDIUM
review_required: false
objective: >
  A live wave applies intended state to both nodes, the drift post-check
  passes, and a rerun reports changed=0.
acceptance:
  - id: A1
    text: lab-verify reports deploy PASS and rerun PASS on SR Linux.
    verified_by: V1
verify:
  - id: V1
    cmd: make lab-cycle LAB=srlinux
    expect: deploy PASS, rerun PASS
out_of_scope:
  - Routing in the live wave
```

`docs/orchestration/tasks/T-015.yaml`:

```yaml
id: T-015
title: SR Linux pre-wave backup and verified restore
implements: [REQ-004, REQ-009]
preserves: [INV-001, INV-004]
addresses: [RISK-001, RISK-002, OPS-001]
baseline: v1
depends_on: [T-014]
owns:
  - roles/live_guard/
  - playbooks/deploy/rollback.yml
must_not_touch:
  - templates/
  - netbox/
shared_owner: false
risk: HIGH
review_required: true
objective: >
  Before any change each node's running datastore is backed up as JSON
  outside the repo; a failed wave replaces / with the backup and proves
  equality.
acceptance:
  - id: A1
    text: Forced post-check failure on a pristine lab restores every node and logs restore verified.
    verified_by: V1
  - id: A2
    text: Unsupported vendor or unset wave id fails before any device change.
    verified_by: V2
verify:
  - id: V1
    cmd: make lab-cycle LAB=srlinux
    expect: drill PASS
  - id: V2
    cmd: pytest scripts/tests/test_live_guard_contract.py -q
    expect: exit 0
out_of_scope:
  - Moving an access port between VLANs (ADR-007 known gap)
```

- [ ] **Step 6: Update T-009..T-011 and state.yaml**

In `docs/orchestration/tasks/T-009.yaml` set
`blocked_on: OWNER corporate Arista account (optional since ACR-006; personal e-mail is rejected)`.
In `T-010.yaml` and `T-011.yaml` leave `blocked_on: T-009` unchanged.

In `docs/orchestration/state.yaml` change the T-009 line's `blocked_on` to
`OWNER corporate Arista account (optional, ACR-006)` and append:

```yaml
  T-012: {status: IN_PROGRESS, validated_baseline: v1, attempts: 1, assigned_to: ORCHESTRATOR}
  T-013: {status: TODO, validated_baseline: v1, attempts: 0, assigned_to: ORCHESTRATOR}
  T-014: {status: TODO, validated_baseline: v1, attempts: 0, assigned_to: ORCHESTRATOR}
  T-015: {status: TODO, validated_baseline: v1, attempts: 0, assigned_to: ORCHESTRATOR}
```

- [ ] **Step 7: Append planning amendments to the spec**

Append to `docs/superpowers/specs/2026-09-23-srlinux-live-lab-design.md`:

```markdown
## Amendments during planning (2026-09-23, from a throwaway spike on 26.7.2)
- Vendor key is `srlinux`, not `srl`: vendor dispatch takes the last segment
  of `ansible_network_os` (`nokia.srlinux.srlinux`). File names follow:
  `lab-srlinux.yml`, `templates/srlinux/`, `srlinux_snapshot.py`, `LAB=srlinux`.
- Root `replace /` is proven; the narrow-path fallback is dropped.
- DNS is `/system/dns-instance[name=clab-default]` (no `/system/dns` on
  26.7); the wave replaces its `server-list`.
- An access port also sets `vlan-tagging: true` on the parent interface
  (required for `untagged` encap).
- The post-check fetches `/` (not five paths): backup, post-check and
  restore proof share one JSON shape and one parser.
- No `templates/srlinux/routing/static.j2`: an SR Linux prefix-set cannot
  express a `deny` sequence, and routing is render-only and fails closed for
  srlinux anyway.
- Containerlab's lab dir must be on the Linux filesystem
  (`CLAB_LABDIR_BASE`), and lab up/verify/down run in one WSL session
  (`make lab-cycle`) because WSL stops idle VMs.
```

- [ ] **Step 8: Lint and commit**

Run: `python -m yamllint -c .yamllint.yml docs`
Expected: exit 0, no output.

```bash
git add docs
git commit -m "docs(acr-006): move live lab to sr linux, add adr-007 and tasks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: srlinux platform in the model

**Files:**
- Create: `netbox/intended/lab-srlinux.yml`
- Modify: `netbox/schema.yml:14`, `scripts/tests/test_validate_model.py`, `Makefile` (`validate` target), `.github/workflows/ci.yml` (validate step)

**Interfaces:**
- Consumes: nothing.
- Produces: `netbox/intended/lab-srlinux.yml` with devices `lab-sw01`, `lab-sw02`, `platform: srlinux`, interface `ethernet-1/1` (description `mgmt-uplink`, access_vlan 99), common ntp `[10.0.0.53]`, dns `[10.0.0.53]`, syslog `[10.0.0.54]`, one VLAN `{id: 99, name: MGMT, vrf: MGMT}`. Tasks 3, 4, 7 read it.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_validate_model.py`:

```python
def test_srlinux_lab_intended_valid():
    res = run(REPO / "netbox" / "intended" / "lab-srlinux.yml")
    assert res.returncode == 0, res.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest scripts/tests/test_validate_model.py -q`
Expected: 1 failed (`test_srlinux_lab_intended_valid`, file not found / rc 1).

- [ ] **Step 3: Create the intended file and allow the platform**

`netbox/intended/lab-srlinux.yml`:

```yaml
# SR Linux lab intended state (T-012, ACR-006). Same intent as lab-eos.yml,
# srlinux platform and interface names. Desired state only (INV-002).
# No secrets in this file (INV-001); credentials come from Vault at runtime.
# Routing sections are omitted on purpose: srlinux has no routing
# implementation and the routing role fails closed for it (ADR-007).
sites:
  - name: LAB-DC1
    description: Containerlab test site
vrfs:
  - name: MGMT
    rd: "65000:99"
vlans:
  - id: 99
    name: MGMT
    vrf: MGMT
prefixes:
  - prefix: 10.0.0.0/24
    vlan: 99
    vrf: MGMT
devices:
  - name: lab-sw01
    site: LAB-DC1
    platform: srlinux
    interfaces:
      - name: ethernet-1/1
        description: mgmt-uplink
        access_vlan: 99
    common:
      ntp_servers: [10.0.0.53]
      dns_servers: [10.0.0.53]
      syslog_servers: [10.0.0.54]
  - name: lab-sw02
    site: LAB-DC1
    platform: srlinux
    interfaces:
      - name: ethernet-1/1
        description: mgmt-uplink
        access_vlan: 99
    common:
      ntp_servers: [10.0.0.53]
      dns_servers: [10.0.0.53]
      syslog_servers: [10.0.0.54]
```

In `netbox/schema.yml` change `platform_allowed: [ios, eos]` to `platform_allowed: [ios, eos, srlinux]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest scripts/tests/test_validate_model.py -q`
Expected: all passed (including `test_unknown_platform_rejected`).

- [ ] **Step 5: Wire the gate**

`Makefile` `validate` target, add a third line:

```make
	python scripts/validate_model.py --schema netbox/schema.yml --input netbox/intended/lab-srlinux.yml
```

`.github/workflows/ci.yml`, after "Validate EOS lab intended state":

```yaml
      - name: Validate SR Linux lab intended state
        run: python scripts/validate_model.py --schema netbox/schema.yml --input netbox/intended/lab-srlinux.yml
```

Run: `make validate && python -m yamllint -c .yamllint.yml .`
Expected: three `OK` lines from validate, yamllint silent.

- [ ] **Step 6: Commit**

```bash
git add netbox scripts/tests/test_validate_model.py Makefile .github/workflows/ci.yml
git commit -m "feat(T-012): add srlinux platform and lab intended state

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: srlinux preview render

**Files:**
- Create: `templates/srlinux/vlan_interface.j2`, `roles/vlan_interface/tests/test_render_srlinux.py`
- Modify: `Makefile` (`render` target), `.github/workflows/ci.yml` (render step), `templates/README.md` (one line)

**Interfaces:**
- Consumes: `netbox/intended/lab-srlinux.yml` (Task 2).
- Produces: `templates/srlinux/vlan_interface.j2` with context `netaut_vlans`, `netaut_interfaces` (same names as ios/eos). Must describe the same effective config as `roles/vlan_interface/tasks/srlinux.yml` (Task 5).

- [ ] **Step 1: Write the failing test**

`roles/vlan_interface/tests/test_render_srlinux.py`:

```python
"""SR Linux VLAN/interface render (T-012): twin of the IOS/EOS render tests."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "srlinux" / "vlan_interface.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-srlinux.yml"


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


def test_vlan_is_a_mac_vrf_named_by_id():
    out = render(context())
    assert "set / network-instance vlan-99 type mac-vrf\n" in out
    assert 'set / network-instance vlan-99 description "MGMT"\n' in out


def test_access_port_is_untagged_bridged_subinterface_in_the_mac_vrf():
    out = render(context())
    for line in ("set / interface ethernet-1/1 admin-state enable",
                 'set / interface ethernet-1/1 description "mgmt-uplink"',
                 "set / interface ethernet-1/1 vlan-tagging true",
                 "set / interface ethernet-1/1 subinterface 0 type bridged",
                 "set / interface ethernet-1/1 subinterface 0 vlan encap untagged",
                 "set / network-instance vlan-99 interface ethernet-1/1.0"):
        assert line + "\n" in out, line


def test_every_line_is_a_flat_set():
    assert all(ln.startswith("set / ") for ln in render(context()).splitlines())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest roles/vlan_interface/tests/test_render_srlinux.py -q`
Expected: 4 errors/failures with `TemplateNotFound: vlan_interface.j2`.

- [ ] **Step 3: Write the template**

`templates/srlinux/vlan_interface.j2`:

```jinja
{% for vlan in netaut_vlans %}
set / network-instance vlan-{{ vlan.id }} type mac-vrf
set / network-instance vlan-{{ vlan.id }} description "{{ vlan.name }}"
{% endfor %}
{% for iface in netaut_interfaces %}
set / interface {{ iface.name }} admin-state enable
set / interface {{ iface.name }} description "{{ iface.description }}"
set / interface {{ iface.name }} vlan-tagging true
set / interface {{ iface.name }} subinterface 0 type bridged
set / interface {{ iface.name }} subinterface 0 vlan encap untagged
set / network-instance vlan-{{ iface.access_vlan }} interface {{ iface.name }}.0
{% endfor %}
```

Add to `templates/README.md` under the vendor list:

```markdown
- `srlinux/` — Nokia SR Linux flat `set /` lines (preview only; waves use `nokia.srlinux.config`). No routing template: a prefix-set cannot express `deny` (ADR-007).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest roles/vlan_interface/tests/test_render_srlinux.py -q`
Expected: 4 passed.

- [ ] **Step 5: Wire the render gate**

`Makefile` `render` target, add:

```make
	python scripts/render_idempotency.py --input netbox/intended/lab-srlinux.yml --vendor srlinux --repo .
```

`.github/workflows/ci.yml`, after "Prove EOS render idempotency":

```yaml
      - name: Prove SR Linux render idempotency
        run: python scripts/render_idempotency.py --input netbox/intended/lab-srlinux.yml --vendor srlinux --repo .
```

Run: `make render`
Expected: last line `render-idempotency OK` three times; srlinux lines `lab-sw01 vlan_interface.j2: IDENTICAL (...)`.

- [ ] **Step 6: Commit**

```bash
git add templates roles/vlan_interface/tests/test_render_srlinux.py Makefile .github/workflows/ci.yml
git commit -m "feat(T-012): add srlinux vlan/interface preview render

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: SR Linux snapshot parser

**Files:**
- Create: `roles/live_guard/files/srlinux_snapshot.py`, `roles/live_guard/tests/fixtures/srlinux/pristine.json`, `roles/live_guard/tests/fixtures/srlinux/clean.json`, `roles/live_guard/tests/test_srlinux_snapshot.py`

**Interfaces:**
- Consumes: `netbox/intended/lab-srlinux.yml` (Task 2), `roles/drift/files/drift.py` CLI (`--intended --operational --report --device --fail-on-drift`; rc 0 no drift, 2 drift, 1 error).
- Produces: `srlinux_snapshot.py` with the same CLI as `eos_snapshot.py`:
  - `--config NAME=PATH` (repeatable) `--out PATH` → writes `{"devices": {NAME: snapshot}, "provenance": "live running datastore (srlinux)"}`; rc 0.
  - `--compare A B` → rc 0 equal, 2 differs; prints only field/section names and counts.
  - rc 1 on unreadable or non-object JSON.
  - `parse(doc: dict) -> {"vlans": [{"id": int, "name": str}], "interfaces": [{"name": str, "access_vlan": int}], "common": {"ntp_servers": [str], "dns_servers": [str], "syslog_servers": [str]}}` (lists sorted).
  - Input file shape: the root running datastore object (`nokia.srlinux.get` of `/` → `result[0]`), written by Task 6.

- [ ] **Step 1: Create fixtures (captured shapes, secrets removed)**

`roles/live_guard/tests/fixtures/srlinux/pristine.json` (a fresh containerlab node, trimmed):

```json
{
  "_annotate": "ACL rules allowing incoming tcp/57411 for the eda-discovery grpc server",
  "srl_nokia-interfaces:interface": [
    {"admin-state": "enable", "name": "mgmt0",
     "subinterface": [{"admin-state": "enable", "index": 0,
                       "ipv4": {"admin-state": "enable", "srl_nokia-interfaces-ip-dhcp:dhcp-client": {}}}]}
  ],
  "srl_nokia-network-instance:network-instance": [
    {"admin-state": "enable", "description": "Management network instance",
     "interface": [{"name": "mgmt0.0"}], "name": "mgmt",
     "type": "srl_nokia-network-instance:ip-vrf"}
  ],
  "srl_nokia-system:system": {
    "srl_nokia-dns:dns-instance": [
      {"name": "clab-default", "network-instance": "mgmt", "server-list": ["10.255.255.254"]}
    ],
    "srl_nokia-logging:logging": {
      "buffer": [{"buffer-name": "messages", "rotate": 3, "size": "10000000"}]
    }
  }
}
```

`roles/live_guard/tests/fixtures/srlinux/clean.json` (after the wave):

```json
{
  "_annotate": "ACL rules allowing incoming tcp/57411 for the eda-discovery grpc server",
  "srl_nokia-interfaces:interface": [
    {"admin-state": "enable", "description": "mgmt-uplink", "name": "ethernet-1/1",
     "srl_nokia-interfaces-vlans:vlan-tagging": true,
     "subinterface": [{"index": 0,
                       "srl_nokia-interfaces-vlans:vlan": {"encap": {"untagged": {}}},
                       "type": "srl_nokia-interfaces:bridged"}]},
    {"admin-state": "enable", "name": "mgmt0",
     "subinterface": [{"admin-state": "enable", "index": 0,
                       "ipv4": {"admin-state": "enable", "srl_nokia-interfaces-ip-dhcp:dhcp-client": {}}}]}
  ],
  "srl_nokia-network-instance:network-instance": [
    {"admin-state": "enable", "description": "Management network instance",
     "interface": [{"name": "mgmt0.0"}], "name": "mgmt",
     "type": "srl_nokia-network-instance:ip-vrf"},
    {"description": "MGMT", "interface": [{"name": "ethernet-1/1.0"}], "name": "vlan-99",
     "type": "srl_nokia-network-instance:mac-vrf"}
  ],
  "srl_nokia-system:system": {
    "srl_nokia-dns:dns-instance": [
      {"name": "clab-default", "network-instance": "mgmt", "server-list": ["10.0.0.53"]}
    ],
    "srl_nokia-logging:logging": {
      "buffer": [{"buffer-name": "messages", "rotate": 3, "size": "10000000"}],
      "network-instance": "mgmt",
      "remote-server": [{"host": "10.0.0.54"}]
    },
    "srl_nokia-ntp:ntp": {"admin-state": "enable", "network-instance": "mgmt",
                          "server": [{"address": "10.0.0.53"}]}
  }
}
```

- [ ] **Step 2: Write the failing tests**

`roles/live_guard/tests/test_srlinux_snapshot.py`:

```python
"""SR Linux running datastore JSON -> operational snapshot (T-012)."""
import copy
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = REPO / "roles" / "live_guard" / "files" / "srlinux_snapshot.py"
DRIFT = REPO / "roles" / "drift" / "files" / "drift.py"
INTENDED = REPO / "netbox" / "intended" / "lab-srlinux.yml"
sys.path.insert(0, str(TOOL.parent))
import srlinux_snapshot  # noqa: E402

FIX = HERE / "fixtures" / "srlinux"
CLEAN_SNAPSHOT = {
    "vlans": [{"id": 99, "name": "MGMT"}],
    "interfaces": [{"name": "ethernet-1/1", "access_vlan": 99}],
    "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],
               "syslog_servers": ["10.0.0.54"]},
}


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                          capture_output=True, text=True)


def test_clean_matches_intended_shape():
    assert srlinux_snapshot.parse(load("clean.json")) == CLEAN_SNAPSHOT


def test_pristine_has_no_vlans_and_keeps_the_clab_dns():
    snap = srlinux_snapshot.parse(load("pristine.json"))
    assert snap["vlans"] == [] and snap["interfaces"] == []
    assert snap["common"] == {"ntp_servers": [], "dns_servers": ["10.255.255.254"],
                              "syslog_servers": []}


def test_prefix_free_document_parses_the_same():
    """Review focus 2: prefixes may come and go between releases."""
    bare = srlinux_snapshot.strip_prefixes(load("clean.json"))
    assert json.dumps(bare).count("srl_nokia-") == 0
    assert srlinux_snapshot.parse(bare) == CLEAN_SNAPSHOT


def test_tagged_subinterface_is_not_an_access_port():
    """Review focus 5: tagged or routed members are not access ports."""
    doc = load("clean.json")
    eth = doc["srl_nokia-interfaces:interface"][0]
    eth["subinterface"][0]["srl_nokia-interfaces-vlans:vlan"] = {
        "encap": {"single-tagged": {"vlan-id": 99}}}
    assert srlinux_snapshot.parse(doc)["interfaces"] == []
    doc = load("clean.json")
    doc["srl_nokia-interfaces:interface"][0]["subinterface"][0]["type"] = "routed"
    assert srlinux_snapshot.parse(doc)["interfaces"] == []


def test_only_mac_vrfs_named_vlan_n_are_vlans():
    doc = load("clean.json")
    nis = doc["srl_nokia-network-instance:network-instance"]
    nis.append({"name": "tenant-a", "type": "srl_nokia-network-instance:mac-vrf"})
    nis.append({"name": "vlan-7", "type": "srl_nokia-network-instance:ip-vrf"})
    assert srlinux_snapshot.parse(doc)["vlans"] == [{"id": 99, "name": "MGMT"}]


def test_vlan_without_description_is_named_after_the_instance():
    doc = load("clean.json")
    del doc["srl_nokia-network-instance:network-instance"][1]["description"]
    assert srlinux_snapshot.parse(doc)["vlans"] == [{"id": 99, "name": "vlan-99"}]


def test_non_ip_values_are_dropped():
    doc = load("clean.json")
    doc["srl_nokia-system:system"]["srl_nokia-ntp:ntp"]["server"].append(
        {"address": "ntp.example.net"})
    assert srlinux_snapshot.parse(doc)["common"]["ntp_servers"] == ["10.0.0.53"]


def test_cli_snapshot_feeds_drift_clean_and_drifted(tmp_path):
    out = tmp_path / "snap.json"
    assert cli("--config", f"lab-sw01={FIX / 'clean.json'}", "--out", out).returncode == 0
    drift = subprocess.run(
        [sys.executable, str(DRIFT), "--intended", str(INTENDED), "--operational", str(out),
         "--report", str(tmp_path / "r.md"), "--device", "lab-sw01", "--fail-on-drift"],
        capture_output=True, text=True)
    assert drift.returncode == 0, drift.stderr
    assert cli("--config", f"lab-sw01={FIX / 'pristine.json'}", "--out", out).returncode == 0
    drift = subprocess.run(
        [sys.executable, str(DRIFT), "--intended", str(INTENDED), "--operational", str(out),
         "--report", str(tmp_path / "r.md"), "--device", "lab-sw01", "--fail-on-drift"],
        capture_output=True, text=True)
    assert drift.returncode == 2


def test_compare_equal_and_parsed_difference():
    assert cli("--compare", FIX / "clean.json", FIX / "clean.json").returncode == 0
    res = cli("--compare", FIX / "pristine.json", FIX / "clean.json")
    assert res.returncode == 2
    assert "vlans" in res.stdout and "common" in res.stdout


def test_compare_catches_a_change_outside_the_parsed_fields(tmp_path):
    doc = load("clean.json")
    doc["srl_nokia-system:system"]["srl_nokia-logging:logging"]["buffer"][0]["rotate"] = 9
    other = tmp_path / "other.json"
    other.write_text(json.dumps(doc), encoding="utf-8")
    res = cli("--compare", FIX / "clean.json", other)
    assert res.returncode == 2
    assert "config sections differ: system" in res.stdout


def test_compare_output_never_contains_config_content(tmp_path):
    """Review focus 4: backups hold hashed secrets; print names and counts only."""
    doc = load("clean.json")
    hashed = "$y$j9T$notarealhashbutlookslikeone"
    doc["srl_nokia-system:system"]["aaa"] = {"authentication": {"user": [
        {"username": "admin", "password": hashed}]}}
    other = tmp_path / "other.json"
    other.write_text(json.dumps(doc), encoding="utf-8")
    res = cli("--compare", FIX / "clean.json", other)
    assert res.returncode == 2
    for needle in (hashed, "10.0.0.53", "mgmt-uplink", "admin"):
        assert needle not in res.stdout + res.stderr


def test_bad_input_is_an_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert cli("--compare", bad, bad).returncode == 1
    bad.write_text("not json", encoding="utf-8")
    assert cli("--config", f"x={bad}", "--out", tmp_path / "o.json").returncode == 1
    assert cli("--config", f"x={tmp_path / 'missing.json'}",
               "--out", tmp_path / "o.json").returncode == 1


def test_parse_does_not_mutate_its_input():
    doc = load("clean.json")
    before = copy.deepcopy(doc)
    srlinux_snapshot.parse(doc)
    assert doc == before
```

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m pytest roles/live_guard/tests/test_srlinux_snapshot.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'srlinux_snapshot'`.

- [ ] **Step 4: Write the parser**

`roles/live_guard/files/srlinux_snapshot.py`:

```python
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
an interface whose subinterface is `bridged` with `untagged` encapsulation and
is a member of such a mac-vrf. NTP/DNS/syslog keep IP values only; DNS is the
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

    members = {}
    for iface in doc.get("interface", []):
        for sub in iface.get("subinterface", []):
            members[f"{iface.get('name')}.{sub.get('index')}"] = (iface.get("name"), sub)

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
    sa, sb = strip_prefixes(a), strip_prefixes(b)
    sections = sorted(k for k in set(sa) | set(sb) if sa.get(k) != sb.get(k))
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
```

Note: the error line prints only the exception type. A `JSONDecodeError` message can quote file content, and a backup holds a password hash.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest roles/live_guard/tests/test_srlinux_snapshot.py -q`
Expected: 13 passed.

Run: `python scripts/secret_scan.py --root .`
Expected: exit 0 (fixtures and tests contain no password or secret assignments).

- [ ] **Step 6: Commit**

```bash
git add roles/live_guard/files/srlinux_snapshot.py roles/live_guard/tests
git commit -m "feat(T-012): parse sr linux running datastore into drift snapshot

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: srlinux role module calls and dispatch

**Files:**
- Create: `roles/common/tasks/srlinux.yml`, `roles/vlan_interface/tasks/srlinux.yml`
- Modify: `roles/common/tasks/main.yml` (vendor assert), `roles/vlan_interface/tasks/main.yml` (vendor assert), `roles/common/defaults/main.yml`, `roles/vlan_interface/defaults/main.yml` (comment only), `scripts/tests/test_role_dispatch.py`, `requirements.yml`

**Interfaces:**
- Consumes: `netaut_common` (`ntp_servers`, `dns_servers`, `syslog_servers`), `netaut_vlans` (`id`, `name`), `netaut_interfaces` (`name`, `description`, `access_vlan`), `netaut_vendor` (from `ansible_network_os`).
- Produces: role defaults `netaut_srlinux_mgmt_instance: mgmt`, `netaut_srlinux_dns_instance: clab-default`. Live effect equals Task 3's template.

- [ ] **Step 1: Write the failing tests**

In `scripts/tests/test_role_dispatch.py` change the `MODULE` regex to

```python
MODULE = re.compile(r"^\s*(cisco\.ios|arista\.eos|nokia\.srlinux)\.", re.M)
```

and append:

```python
SRLINUX_ROLES = ["common", "vlan_interface"]


def srlinux_tasks(role):
    return yaml.safe_load((REPO / "roles" / role / "tasks" / "srlinux.yml")
                          .read_text(encoding="utf-8"))


def test_srlinux_exists_only_for_live_roles_and_routing_fails_closed():
    for role in SRLINUX_ROLES:
        assert (REPO / "roles" / role / "tasks" / "srlinux.yml").is_file(), role
    assert not (REPO / "roles" / "routing" / "tasks" / "srlinux.yml").exists()
    routing = (REPO / "roles" / "routing" / "tasks" / "main.yml").read_text(encoding="utf-8")
    assert "'srlinux'" not in routing


def test_supported_vendor_asserts_include_srlinux():
    for role in SRLINUX_ROLES:
        tasks = yaml.safe_load((REPO / "roles" / role / "tasks" / "main.yml")
                               .read_text(encoding="utf-8"))
        vendor = next(t for t in tasks if t["name"] == "Require a supported vendor (fail closed)")
        assert vendor["ansible.builtin.assert"]["that"] == [
            "netaut_vendor in ['ios', 'eos', 'srlinux']"], role


def test_srlinux_files_only_call_config_and_never_save():
    for role in SRLINUX_ROLES:
        for task in srlinux_tasks(role):
            modules = [k for k in task if "." in k]
            assert modules == ["nokia.srlinux.config"], (role, task["name"])
            assert task["nokia.srlinux.config"]["save_when"] == "never", (role, task["name"])


def test_srlinux_access_port_matches_the_template():
    """Role and template must converge on the same access-port shape."""
    task = next(t for t in srlinux_tasks("vlan_interface")
                if t["name"] == "Ensure access interfaces")
    iface, member = task["nokia.srlinux.config"]["update"]
    assert iface["path"] == "/interface[name={{ item.name }}]"
    assert iface["value"]["vlan-tagging"] is True
    sub = iface["value"]["subinterface"][0]
    assert sub == {"index": 0, "type": "bridged", "vlan": {"encap": {"untagged": {}}}}
    assert member["path"] == "/network-instance[name=vlan-{{ item.access_vlan }}]"
    assert member["value"] == {"interface": [{"name": "{{ item.name }}.0"}]}


def test_srlinux_vlan_is_mac_vrf_named_by_id():
    task = next(t for t in srlinux_tasks("vlan_interface") if t["name"] == "Ensure VLANs exist")
    (vlan,) = task["nokia.srlinux.config"]["update"]
    assert vlan["path"] == "/network-instance[name=vlan-{{ item.id }}]"
    assert vlan["value"] == {"type": "mac-vrf", "description": "{{ item.name }}"}


def test_srlinux_dns_replaces_the_server_list():
    task = next(t for t in srlinux_tasks("common") if t["name"] == "Configure DNS name servers")
    (dns,) = task["nokia.srlinux.config"]["replace"]
    assert dns["path"].endswith("/server-list")
    assert dns["value"] == "{{ netaut_common.dns_servers }}"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest scripts/tests/test_role_dispatch.py -q`
Expected: the 6 new tests fail (files missing / assert lists lack `srlinux`); the old 4 pass.

- [ ] **Step 3: Write the module calls**

`roles/common/tasks/srlinux.yml`:

```yaml
---
# SR Linux module calls for common settings (T-012). Module arguments only
# (INV-003). All three services use the management network-instance.
# DNS replaces the server-list of the instance containerlab already created
# (26.7 has /system/dns-instance, no /system/dns); update would keep stale
# servers and the post-check would report drift.
- name: Configure NTP servers
  nokia.srlinux.config:
    update:
      - path: /system/ntp
        value:
          admin-state: enable
          network-instance: "{{ netaut_srlinux_mgmt_instance }}"
          server: "{{ netaut_common.ntp_servers | map('community.general.dict_kv', 'address') | list }}"
    save_when: never

- name: Configure DNS name servers
  nokia.srlinux.config:
    update:
      - path: "/system/dns-instance[name={{ netaut_srlinux_dns_instance }}]"
        value:
          network-instance: "{{ netaut_srlinux_mgmt_instance }}"
    replace:
      - path: "/system/dns-instance[name={{ netaut_srlinux_dns_instance }}]/server-list"
        value: "{{ netaut_common.dns_servers }}"
    save_when: never

- name: Configure syslog hosts
  nokia.srlinux.config:
    update:
      - path: /system/logging
        value:
          network-instance: "{{ netaut_srlinux_mgmt_instance }}"
          remote-server: "{{ netaut_common.syslog_servers | map('community.general.dict_kv', 'host') | list }}"
    save_when: never
```

Note: the DNS test destructures `replace` as a single entry and does not read `update`; the `update` entry makes sure the instance exists with its mandatory `network-instance` leaf before the list is replaced (the module applies replaces before updates in one transaction, and both land in one commit).

`roles/vlan_interface/tasks/srlinux.yml`:

```yaml
---
# SR Linux module calls for VLANs and access ports (T-012). Module arguments
# only (INV-003). A VLAN is a mac-vrf named vlan-<id>; an access port is a
# bridged, untagged subinterface 0 that is a member of that mac-vrf.
# SR Linux accepts untagged encap only with vlan-tagging on the parent.
# Moving a port to another VLAN fails the commit (ADR-007 known gap).
- name: Ensure VLANs exist
  nokia.srlinux.config:
    update:
      - path: "/network-instance[name=vlan-{{ item.id }}]"
        value:
          type: mac-vrf
          description: "{{ item.name }}"
    save_when: never
  loop: "{{ netaut_vlans }}"

- name: Ensure access interfaces
  nokia.srlinux.config:
    update:
      - path: "/interface[name={{ item.name }}]"
        value:
          admin-state: enable
          description: "{{ item.description }}"
          vlan-tagging: true
          subinterface:
            - index: 0
              type: bridged
              vlan:
                encap:
                  untagged: {}
      - path: "/network-instance[name=vlan-{{ item.access_vlan }}]"
        value:
          interface:
            - name: "{{ item.name }}.0"
    save_when: never
  loop: "{{ netaut_interfaces }}"
```

- [ ] **Step 4: Asserts, defaults, requirements**

In `roles/common/tasks/main.yml` and `roles/vlan_interface/tasks/main.yml` change `netaut_vendor in ['ios', 'eos']` to `netaut_vendor in ['ios', 'eos', 'srlinux']`.

Append to `roles/common/defaults/main.yml`:

```yaml
# SR Linux (T-012): management network-instance, and the DNS instance the
# wave owns. clab-default is the instance containerlab creates on every node.
netaut_srlinux_mgmt_instance: mgmt
netaut_srlinux_dns_instance: clab-default
```

In both `roles/common/defaults/main.yml` and `roles/vlan_interface/defaults/main.yml` change the comment `# Vendor dispatch (T-008): ios | eos, from ansible_network_os.` to `# Vendor dispatch (T-008, T-012): ios | eos | srlinux, from ansible_network_os.`

Append to `requirements.yml`:

```yaml
  # SR Linux JSON-RPC modules (T-012, ADR-007). Exact pin: proven on
  # SR Linux 26.7.2 during planning (config idempotency, root replace).
  - name: nokia.srlinux
    version: "1.1.1"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest scripts/tests/test_role_dispatch.py -q`
Expected: 10 passed.

Run: `make gates`
Expected: exit 0 (lint, scan, validate, render, test all green).

- [ ] **Step 6: Commit**

```bash
git add roles/common roles/vlan_interface scripts/tests/test_role_dispatch.py requirements.yml
git commit -m "feat(T-012): add srlinux module calls to common and vlan_interface

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: live_guard for srlinux (backup, fetch, restore)

**Files:**
- Create: `roles/live_guard/tasks/srlinux/backup.yml`, `fetch.yml`, `restore.yml`
- Modify: `roles/live_guard/defaults/main.yml`, `roles/live_guard/tasks/backup.yml`, `roles/live_guard/tasks/postcheck.yml`, `roles/live_guard/tasks/restore.yml`, `roles/live_guard/tasks/eos/backup.yml`, `roles/live_guard/README.md`, `scripts/tests/test_live_guard_contract.py`

**Interfaces:**
- Consumes: `srlinux_snapshot.py` CLI (Task 4); `netaut_backup_dir`, `netaut_run_dir`, `netaut_wave`, `netaut_vendor`, `live_guard_files`, `live_guard_drift` (existing defaults).
- Produces: `live_guard_ext` default (`json` for srlinux, `cfg` otherwise). Backup file `{{ netaut_backup_dir }}/{{ inventory_hostname }}-{{ netaut_wave }}.{{ live_guard_ext }}`. Fetch writes the root document JSON to `live_guard_fetch_to`. Existing entry points `backup`, `postcheck`, `restore` accept `srlinux`.

- [ ] **Step 1: Write the failing tests**

In `scripts/tests/test_live_guard_contract.py` change both expected guard lists from `"netaut_vendor in ['eos']"` to `"netaut_vendor in ['eos', 'srlinux']"`, extend the imports at the top of the file to

```python
import json
import pathlib
import shutil
import subprocess

import pytest
import yaml
```

then append:

```python
def test_backup_paths_use_the_vendor_extension():
    defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
    assert "live_guard_ext:" in defaults
    for entry in ("backup.yml", "postcheck.yml", "restore.yml", "eos/backup.yml"):
        text = (TASKS / entry).read_text(encoding="utf-8")
        assert ".cfg" not in text, entry
        assert "live_guard_ext" in text, entry


def test_srlinux_secret_tasks_are_no_log():
    """Review focus 4: backups and fetches carry the admin password hash."""
    for action in ("backup", "fetch", "restore"):
        for task in load(TASKS / "srlinux" / f"{action}.yml"):
            if any(k.startswith("nokia.srlinux.") or k == "ansible.builtin.copy" for k in task):
                assert task.get("no_log") is True, (action, task["name"])


def test_srlinux_restore_replaces_root_and_never_saves():
    (task,) = [t for t in load(TASKS / "srlinux" / "restore.yml")
               if "nokia.srlinux.config" in t]
    cfg = task["nokia.srlinux.config"]
    assert cfg["replace"][0]["path"] == "/"
    assert cfg["save_when"] == "never"


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="needs ansible-core")
def test_srlinux_restore_value_is_not_templated(tmp_path):
    """Review focus 1: braces in the backup must reach the device verbatim."""
    (task,) = [t for t in load(TASKS / "srlinux" / "restore.yml")
               if "nokia.srlinux.config" in t]
    expr = task["nokia.srlinux.config"]["replace"][0]["value"]
    backup = tmp_path / "b.json"
    backup.write_text(json.dumps({"system": {"banner": {"login-banner": "{{ 6 * 7 }}"}}}),
                      encoding="utf-8")
    result = tmp_path / "out.json"
    play = [{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"netaut_backup_file": backup.as_posix(), "restored": expr},
        "tasks": [{"ansible.builtin.copy": {
            "content": "{{ restored | to_json }}", "dest": result.as_posix()}}],
    }]
    path = tmp_path / "p.yml"
    path.write_text(yaml.safe_dump(play), encoding="utf-8")
    res = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-2000:]
    restored = json.loads(result.read_text(encoding="utf-8"))
    assert restored["system"]["banner"]["login-banner"] == "{{ 6 * 7 }}"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest scripts/tests/test_live_guard_contract.py -q`
Expected: the two guard tests fail (`['eos']` vs `['eos', 'srlinux']`), the extension test fails (`.cfg` found), the three srlinux tests fail (`FileNotFoundError` for `tasks/srlinux/...`). `test_every_vendor_dir_implements_all_actions` still passes.

- [ ] **Step 3: Vendor extension and asserts**

Append to `roles/live_guard/defaults/main.yml`:

```yaml
# Backup/fetch file extension per vendor (T-015): eos keeps text configs,
# srlinux keeps the running datastore as JSON.
live_guard_ext: "{{ {'srlinux': 'json'}.get(netaut_vendor, 'cfg') }}"
```

In `roles/live_guard/tasks/backup.yml`, `postcheck.yml` and `restore.yml`: replace every `netaut_vendor in ['eos']` with `netaut_vendor in ['eos', 'srlinux']`, and replace every `.cfg"` in a path with `.{{ live_guard_ext }}"`. Concretely:
- `backup.yml`: both stat paths become `"{{ netaut_backup_dir }}/{{ inventory_hostname }}-{{ netaut_wave }}.{{ live_guard_ext }}"`.
- `postcheck.yml`: `-post.cfg` → `-post.{{ live_guard_ext }}` (two places).
- `restore.yml`: `-restored.cfg` → `-restored.{{ live_guard_ext }}` (two places).
- `eos/backup.yml`: `filename: "{{ inventory_hostname }}-{{ netaut_wave }}.{{ live_guard_ext }}"`.

- [ ] **Step 4: srlinux vendor actions**

`roles/live_guard/tasks/srlinux/backup.yml`:

```yaml
---
# SR Linux pre-wave backup (T-015). Reads only; the device is not changed.
# The whole running datastore as JSON; restore replaces / with it. It holds
# the admin password hash, so nothing here is ever logged (INV-001).
- name: Read running datastore
  nokia.srlinux.get:
    paths:
      - path: /
        datastore: running
  register: live_guard_backup_read
  no_log: true

- name: Save running datastore
  ansible.builtin.copy:
    content: "{{ live_guard_backup_read.result[0] | to_nice_json(sort_keys=true) }}\n"
    dest: "{{ netaut_backup_dir }}/{{ inventory_hostname }}-{{ netaut_wave }}.{{ live_guard_ext }}"
    mode: "0600"
  delegate_to: localhost
  changed_when: false
  no_log: true
```

`roles/live_guard/tasks/srlinux/fetch.yml`:

```yaml
---
# SR Linux running datastore fetch (T-014). Input: live_guard_fetch_to
# (local path). Same shape as the backup, so one parser serves post-check
# and restore proof. Never logged: it holds the admin password hash.
- name: Read running datastore
  nokia.srlinux.get:
    paths:
      - path: /
        datastore: running
  register: live_guard_running
  no_log: true

- name: Store fetched running datastore locally
  ansible.builtin.copy:
    content: "{{ live_guard_running.result[0] | to_nice_json(sort_keys=true) }}\n"
    dest: "{{ live_guard_fetch_to }}"
    mode: "0600"
  delegate_to: localhost
  changed_when: false
  no_log: true
```

`roles/live_guard/tasks/srlinux/restore.yml`:

```yaml
---
# SR Linux restore (T-015): replace / with the backup in one commit, so the
# device lands exactly on the backup, not a merge of backup and wave (proven
# byte-equal on 26.7.2). The file lookup is data, not a template: braces in
# descriptions or banners reach the device verbatim (contract-tested).
- name: Replace running datastore with backup
  nokia.srlinux.config:
    replace:
      - path: /
        value: "{{ lookup('ansible.builtin.file', netaut_backup_file) | from_json }}"
    save_when: never
  no_log: true
```

Add to `roles/live_guard/README.md` a line under the vendor list:

```markdown
- `srlinux/` (T-014/T-015): `get /` backup as JSON, `replace /` restore, `srlinux_snapshot.py` post-check and restore proof.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest scripts/tests/test_live_guard_contract.py roles/live_guard -q`
Expected: all passed. If `test_srlinux_restore_value_is_not_templated` fails, the restore expression renders the braces: stop and report, do not weaken the test (it guards Review Focus 1).

Run: `make gates`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add roles/live_guard scripts/tests/test_live_guard_contract.py
git commit -m "feat(T-015): add srlinux backup, fetch and root-replace restore

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: SR Linux lab bring-up

**Files:**
- Create: `lab/netaut-srlinux.clab.yml`, `inventories/lab-srlinux.yml`
- Modify: `scripts/lab_vault.sh`, `scripts/lab_verify.py`, `scripts/tests/test_lab_verify.py`, `Makefile` (lab section), `.github/workflows/ci.yml` (syntax + dry-run)

**Interfaces:**
- Consumes: everything above.
- Produces: `make lab-up|lab-vault|lab-verify|lab-down|lab-cycle LAB=srlinux|eos`. `lab_verify.py` gains `inventory_hosts(path) -> dict[str, str]`, `wait_ready(addrs: dict[str, str], port: int, timeout: float, connect=..., sleep=..., clock=...) -> list[str]` (hosts still not ready), and flags `--wait-port`, `--wait-seconds`, `--image`.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/tests/test_lab_verify.py`:

```python
REPO = pathlib.Path(__file__).resolve().parents[2]


def test_inventory_hosts_reads_nested_groups():
    assert lab_verify.inventory_hosts(REPO / "inventories" / "lab-srlinux.yml") == {
        "lab-sw01": "172.20.21.11", "lab-sw02": "172.20.21.12"}


def test_wait_ready_returns_hosts_that_never_answer():
    now = [0.0]

    def connect(addr, timeout):
        if addr[0] == "10.0.0.2":
            raise OSError("refused")

        class Sock:
            def close(self):
                pass
        return Sock()

    def sleep(seconds):
        now[0] += seconds

    left = lab_verify.wait_ready({"a": "10.0.0.1", "b": "10.0.0.2"}, 443, 30,
                                 connect=connect, sleep=sleep, clock=lambda: now[0])
    assert left == ["b"]


def test_main_fails_before_any_play_when_a_host_is_not_ready(monkeypatch, capsys):
    """Review focus 3: an unready lab stops lab-verify before any wave."""
    monkeypatch.setattr(lab_verify, "wait_ready", lambda *a, **k: ["lab-sw02"])
    monkeypatch.setattr(lab_verify, "play",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("play ran")))
    rc = lab_verify.main(["--inventory", str(REPO / "inventories" / "lab-srlinux.yml"),
                          "--wave", "W-t", "--wait-port", "443", "--image", "img:1"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "image: img:1" in out
    assert "not ready: lab-sw02" in out
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest scripts/tests/test_lab_verify.py -q`
Expected: the 3 new tests fail (`inventory_hosts` missing / inventory file missing).

- [ ] **Step 3: Topology and inventory**

`lab/netaut-srlinux.clab.yml`:

```yaml
# Free live lab (T-013, ADR-007). Public image, no account needed.
# Deploy through `make lab-up LAB=srlinux`: it puts containerlab's lab dir on
# the Linux filesystem (CLAB_LABDIR_BASE). Under /mnt/c SR Linux cannot set
# file permissions and its startup commit fails, so JSON-RPC never opens.
name: netaut-srlinux
mgmt:
  network: netaut-srlinux-mgmt
  ipv4-subnet: 172.20.21.0/24
topology:
  kinds:
    nokia_srlinux:
      image: ${SRLINUX_IMAGE:=ghcr.io/nokia/srlinux:26.7.2}
  nodes:
    lab-sw01:
      kind: nokia_srlinux
      mgmt-ipv4: 172.20.21.11
    lab-sw02:
      kind: nokia_srlinux
      mgmt-ipv4: 172.20.21.12
  links:
    - endpoints: ["lab-sw01:e1-1", "lab-sw02:e1-1"]
```

`inventories/lab-srlinux.yml`:

```yaml
# SR Linux lab inventory (T-013, ADR-007). Connection details only; the
# login comes from the encrypted ~/.netaut/lab-vault-srlinux.yml at runtime
# (INV-001). validate_certs is off only because containerlab issues a
# self-signed lab certificate: a lab-only exception (ADR-007).
all:
  children:
    lab:
      children:
        srlinux:
          hosts:
            lab-sw01:
              ansible_host: 172.20.21.11
            lab-sw02:
              ansible_host: 172.20.21.12
          vars:
            ansible_network_os: nokia.srlinux.srlinux
            ansible_connection: ansible.netcommon.httpapi
            ansible_httpapi_use_ssl: true
            ansible_httpapi_validate_certs: false
            netaut_intended_file: "{{ inventory_dir }}/../netbox/intended/lab-srlinux.yml"
      vars:
        ansible_user: "{{ vault_lab_user | default('admin') }}"
```

- [ ] **Step 4: lab_verify readiness and image line**

In `scripts/lab_verify.py` add `import socket`, `import time`, `import yaml` to the imports and these functions above `main`:

```python
def inventory_hosts(path) -> dict[str, str]:
    """Host -> ansible_host from a YAML inventory, walking nested children."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    found: dict[str, str] = {}

    def walk(group: dict) -> None:
        for name, hvars in (group.get("hosts") or {}).items():
            found[name] = (hvars or {}).get("ansible_host", name)
        for child in (group.get("children") or {}).values():
            walk(child or {})

    walk(data.get("all", {}))
    return found


def wait_ready(addrs: dict[str, str], port: int, timeout: float,
               connect=socket.create_connection, sleep=time.sleep,
               clock=time.monotonic) -> list[str]:
    """Poll each host's TCP port until it accepts or timeout; return the rest."""
    pending = dict(addrs)
    deadline = clock() + timeout
    while pending:
        for name, addr in list(pending.items()):
            try:
                connect((addr, port), timeout=3).close()
                del pending[name]
            except OSError:
                pass
        if not pending or clock() >= deadline:
            break
        sleep(5)
    return sorted(pending)
```

In `main`, add the arguments after `--vault-args`:

```python
    parser.add_argument("--wait-port", type=int, default=0,
                        help="TCP port that must answer on every host before any play (0 = no wait)")
    parser.add_argument("--wait-seconds", type=float, default=300)
    parser.add_argument("--image", default="", help="lab image, recorded in the evidence")
```

and insert right after `args = parser.parse_args(argv)`:

```python
    if args.image:
        print(f"image: {args.image}")
    if args.wait_port:
        left = wait_ready(inventory_hosts(args.inventory), args.wait_port, args.wait_seconds)
        if left:
            print(f"not ready: {', '.join(left)} (port {args.wait_port}); no wave started")
            print("lab-verify FAILED")
            return 1
        print(f"ready: all hosts answer on port {args.wait_port}")
```

Also change the module docstring's first line to `"""Live lab verification (T-010/T-011, T-014/T-015). Runs inside WSL against a running lab.` and the `--inventory` default stays `inventories/lab-eos.yml` (the Makefile always passes it).

- [ ] **Step 5: Vault script takes the login**

In `scripts/lab_vault.sh` replace the header comment's login sentence and the argument block:

```bash
# Create the lab vault once (T-009, T-013, INV-001). Everything lands outside
# the repo under ~/.netaut and nothing is echoed. The login is the lab kind's
# well-known containerlab default (cEOS admin/admin, SR Linux admin/NokiaSrl1!),
# not a real secret, but it still goes through Vault so the inventory path is
# identical for real devices.
set -euo pipefail
vault_file="${1:?vault file path}"
pass_file="${2:?vault password file path}"
login="${3:-admin}"
```

and change the `printf` line to:

```bash
  printf 'ansible_%s: %s\n' "password" "$login"
```

- [ ] **Step 6: Makefile lab section**

Replace everything from `# Live lab (T-009..T-011, ADR-006).` to the end of `Makefile` with:

```make
# Live lab (T-009..T-011 cEOS / ADR-006, T-013..T-015 SR Linux / ADR-007).
# Run inside WSL. LAB=srlinux (default, public image) or LAB=eos (image
# imported by the OWNER: docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>).
# Vault material and containerlab's lab dir stay under ~/.netaut, outside the
# repo (INV-001); SR Linux cannot boot with its lab dir under /mnt/c.
# WSL stops the VM when the last session ends: use lab-cycle from Windows.
# No sudo: members of the clab_admins group run containerlab directly.
LAB ?= srlinux
CEOS_IMAGE ?= ceos:latest
SRLINUX_IMAGE ?= ghcr.io/nokia/srlinux:26.7.2
LAB_TOPO_eos := lab/netaut.clab.yml
LAB_TOPO_srlinux := lab/netaut-srlinux.clab.yml
LAB_INV_eos := inventories/lab-eos.yml
LAB_INV_srlinux := inventories/lab-srlinux.yml
LAB_PORT_eos := 22
LAB_PORT_srlinux := 443
LAB_IMAGE_eos = $(CEOS_IMAGE)
LAB_IMAGE_srlinux = $(SRLINUX_IMAGE)
# Well-known containerlab default logins, not secrets; routed through Vault.
LAB_LOGIN_eos := admin
LAB_LOGIN_srlinux := NokiaSrl1!
LAB_VAULT ?= $(HOME)/.netaut/lab-vault-$(LAB).yml
LAB_VAULT_PASS ?= $(HOME)/.netaut/vault_pass
export CLAB_LABDIR_BASE ?= $(HOME)/.netaut/clab
WAVE ?= W-$(shell date +%Y%m%d-%H%M%S)

lab-up:
	mkdir -p $(CLAB_LABDIR_BASE)
	CEOS_IMAGE=$(CEOS_IMAGE) SRLINUX_IMAGE=$(SRLINUX_IMAGE) \
	  containerlab deploy -t $(LAB_TOPO_$(LAB)) --reconfigure

lab-down:
	containerlab destroy -t $(LAB_TOPO_$(LAB)) --cleanup

lab-vault:
	scripts/lab_vault.sh $(LAB_VAULT) $(LAB_VAULT_PASS) '$(LAB_LOGIN_$(LAB))'

lab-verify:
	python3 scripts/lab_verify.py --inventory $(LAB_INV_$(LAB)) --wave $(WAVE) \
	  --wait-port $(LAB_PORT_$(LAB)) --image $(LAB_IMAGE_$(LAB)) \
	  --vault-args "-e @$(LAB_VAULT) --vault-password-file $(LAB_VAULT_PASS)"

# One WSL session: up, vault, verify, always down; exit code is lab-verify's.
lab-cycle:
	$(MAKE) lab-up LAB=$(LAB)
	$(MAKE) lab-vault LAB=$(LAB)
	$(MAKE) lab-verify LAB=$(LAB) WAVE=$(WAVE); rc=$$?; \
	  $(MAKE) lab-down LAB=$(LAB); exit $$rc
```

Update the `.PHONY` line to include `lab-cycle`, and the `help` target's lab line to
`@echo "lab (inside WSL, LAB=srlinux|eos): lab-up | lab-vault | lab-verify | lab-down | lab-cycle"`.

- [ ] **Step 7: CI steps for the new inventory**

In `.github/workflows/ci.yml` "Ansible syntax checks", add the line:

```yaml
          ansible-playbook playbooks/deploy/site.yml -i inventories/lab-srlinux.yml --syntax-check
```

and after "EOS deploy dry run" add:

```yaml
      - name: SR Linux deploy dry run (render-only, no devices touched)
        env:
          ANSIBLE_ROLES_PATH: roles
        run: ansible-playbook playbooks/deploy/site.yml -i inventories/lab-srlinux.yml --check --diff
```

- [ ] **Step 8: Run device-less checks**

Run: `python -m pytest scripts/tests/test_lab_verify.py -q`
Expected: all passed.

Run: `make gates`
Expected: exit 0. `secret_scan` must stay green: `LAB_LOGIN_srlinux` does not match the `password` pattern, and the vault script keeps the `printf 'ansible_%s'` indirection.

Run inside WSL (see "Running in WSL" below), with the collections installed first:
`ansible-galaxy collection install -r requirements.yml && ANSIBLE_ROLES_PATH=roles ansible-playbook playbooks/deploy/site.yml -i inventories/lab-srlinux.yml --check --diff`
Expected: `failed=0` for lab-sw01, lab-sw02 and localhost; live tasks skipped.

- [ ] **Step 9: Live bring-up evidence (T-013)**

Running in WSL: write a script to the session scratchpad and run it with PowerShell as `wsl -d Ubuntu -- bash -l /mnt/c/<scratchpad>/t013.sh` (Git Bash mangles `/mnt` paths; Ansible ignores `ansible.cfg` in the world-writable `/mnt/c` repo dir, hence `ANSIBLE_ROLES_PATH=roles`). Script body:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd /mnt/c/Users/mesut/Desktop/workspace/A-projects/netaut
{
  echo "# T-013 evidence $(date -Iseconds)"
  containerlab version | grep -i '^ *version'
  make lab-up LAB=srlinux 2>&1 | tail -8
  make lab-vault LAB=srlinux
  python3 -c "import sys; sys.path.insert(0,'scripts'); import lab_verify as l; \
left=l.wait_ready(l.inventory_hosts('inventories/lab-srlinux.yml'),443,300); \
print('not ready:',left) if left else print('ready: lab-sw01 lab-sw02 answer on 443')"
  containerlab inspect -t lab/netaut-srlinux.clab.yml 2>&1 | tail -8
  make lab-down LAB=srlinux 2>&1 | tail -2
} 2>&1 | tee reports/T-013.txt
```

Expected in `reports/T-013.txt`: two nodes `running` with `ghcr.io/nokia/srlinux:26.7.2`, `ready: lab-sw01 lab-sw02 answer on 443`, then destroy. If the vault already exists from an earlier cEOS attempt at `~/.netaut/lab-vault.yml`, it is ignored: the srlinux vault is `~/.netaut/lab-vault-srlinux.yml`.

- [ ] **Step 10: Commit**

```bash
git add lab inventories scripts Makefile .github/workflows/ci.yml reports/T-013.txt
git commit -m "feat(T-013): bring up sr linux lab with readiness wait and lab-cycle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Live proof, review, records

**Files:**
- Create: `reports/T-012.txt`, `reports/T-014.txt`, `reports/T-015.txt`, `reports/reviews/T-015.md`
- Modify: `docs/orchestration/state.yaml`, `README.md`, `docs/runbook.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: everything above.
- Produces: evidence that closes T-012..T-015.

- [ ] **Step 1: Device-less evidence (T-012)**

Run: `make gates 2>&1 | tee reports/T-012.txt`
Expected: exit 0; file ends with the pytest summary line (`N passed`).

- [ ] **Step 2: Full live cycle (T-014 + T-015)**

Same WSL pattern as Task 7 Step 9, script body:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd /mnt/c/Users/mesut/Desktop/workspace/A-projects/netaut
make lab-cycle LAB=srlinux 2>&1 | tee /tmp/netaut-cycle.txt
rc=${PIPESTATUS[0]}
grep -E '^(image|ready|not ready|drill|deploy|rerun|lab-verify)' /tmp/netaut-cycle.txt > /tmp/netaut-summary.txt
{ echo "# T-014 evidence $(date -Iseconds) (rc=$rc)"; grep -E '^(image|ready|deploy|rerun|lab-verify)' /tmp/netaut-summary.txt; } > reports/T-014.txt
{ echo "# T-015 evidence $(date -Iseconds) (rc=$rc)"; grep -E '^(image|ready|drill|lab-verify)' /tmp/netaut-summary.txt; } > reports/T-015.txt
cat /tmp/netaut-summary.txt
exit $rc
```

Expected:

```
image: ghcr.io/nokia/srlinux:26.7.2
ready: all hosts answer on port 443
drill: PASS (rc=2 restore_verified=True)
deploy: PASS (rc=0)
rerun: PASS (rc=0 changed={'lab-sw01': 0, 'lab-sw02': 0, 'localhost': 0})
lab-verify OK: all live checks passed
```

(`drill` rc is whatever non-zero `ansible-playbook` returns for a failed host, usually 2.) Only the summary lines are committed: the full log never leaves `/tmp`, because a failed run prints play output. Do not commit `/tmp/netaut-cycle.txt`.

If a check FAILS: follow superpowers:systematic-debugging using `/tmp/netaut-cycle.txt`. Likely spots: `community.general` missing in WSL (`ansible-galaxy collection install -r requirements.yml`), the `dns-instance` name (check `get /system/dns-instance`), or `changed` on rerun from a leaf the device normalises (compare the second run's diff with `-vvv --diff` on one host). Fix in the owning task's files, rerun `make gates`, then rerun this step.

- [ ] **Step 3: HIGH-risk review for T-015**

Use superpowers:requesting-code-review on the branch diff for `roles/live_guard/`, `roles/live_guard/files/srlinux_snapshot.py` and `scripts/tests/test_live_guard_contract.py`, with ADR-005, ADR-007 and this plan's Review Focus as the brief. Write the findings and their fixes to `reports/reviews/T-015.md` in the format of `reports/reviews/T-011.md`. Fix every finding (TDD), rerun Step 1 and Step 2, and regenerate the evidence files.

- [ ] **Step 4: Close the tasks**

In `docs/orchestration/state.yaml` set:

```yaml
  T-012: {status: DONE, validated_baseline: v1, attempts: 1, assigned_to: ORCHESTRATOR, verified_by: ORCHESTRATOR, verification_evidence: reports/T-012.txt}
  T-013: {status: DONE, validated_baseline: v1, attempts: 1, assigned_to: ORCHESTRATOR, verified_by: ORCHESTRATOR, verification_evidence: reports/T-013.txt}
  T-014: {status: DONE, validated_baseline: v1, attempts: 1, assigned_to: ORCHESTRATOR, verified_by: ORCHESTRATOR, verification_evidence: reports/T-014.txt}
  T-015: {status: DONE, validated_baseline: v1, attempts: 1, assigned_to: ORCHESTRATOR, verified_by: ORCHESTRATOR, verification_evidence: reports/T-015.txt, reviewed_by: REVIEW_AGENT, review_evidence: reports/reviews/T-015.md}
```

(`attempts` is the real number of live-cycle attempts, max 2 per `state.yaml`.)

- [ ] **Step 5: README, runbook, changelog**

`README.md`:
- Layout table: `netbox/` row add `` `intended/lab-srlinux.yml` (srlinux) ``; `inventories/` row add `` `lab-srlinux.yml` (SR Linux lab) ``; `lab/` row becomes `` Containerlab topologies: 2x SR Linux (default, ADR-007), 2x Arista cEOS (optional, ADR-006) ``.
- Replace the "## Live lab (cEOS, free)" section with:

````markdown
## Live lab (SR Linux, free)

Runs in WSL Ubuntu with Docker and containerlab. The SR Linux image is public; no account.

```bash
ansible-galaxy collection install -r requirements.yml
make lab-cycle              # up -> vault -> drill (restore) -> deploy -> rerun changed=0 -> down
```

Step by step (keep one WSL session open, WSL stops idle VMs): `make lab-up`,
`make lab-vault`, `make lab-verify`, `make lab-down`. `LAB=eos` runs the same on
cEOS, which needs an image from a corporate arista.com account.
````

- Roadmap line: `→ 5. Live lab with backup/restore: SR Linux done (T-012..T-015); cEOS built, optional (T-009..T-011).`

`docs/runbook.md` section 3: retitle `## 3. Live wave (SR Linux lab, ACR-006; cEOS optional)`, and in the command replace `inventories/lab-eos.yml` with `inventories/lab-srlinux.yml` and `~/.netaut/lab-vault.yml` with `~/.netaut/lab-vault-srlinux.yml`; `make lab-up CEOS_IMAGE=ceos:<ver>` becomes `make lab-up` (SR Linux) with `make lab-up LAB=eos CEOS_IMAGE=ceos:<ver>` as the cEOS alternative; `make lab-verify` becomes `make lab-cycle`.

`CHANGELOG.md`, insert above "## Unreleased (cEOS live lab, ACR-005)":

```markdown
## Unreleased (SR Linux live lab, ACR-006)

- T-012: srlinux platform, preview render, role module calls (nokia.srlinux 1.1.1), JSON snapshot parser
- T-013: containerlab SR Linux topology, httpapi inventory, `LAB=` switch, readiness wait, `make lab-cycle`
- T-014/T-015: live wave, drift post-check, root-replace restore with proof; first live evidence
- Review: reports/reviews/T-015.md
- Decisions: ACR-006, ADR-007 (cEOS optional)
```

- [ ] **Step 6: Final gates and commit**

Run: `make gates && python -m yamllint -c .yamllint.yml .`
Expected: exit 0.

```bash
git add reports docs README.md CHANGELOG.md
git commit -m "docs(T-015): record sr linux live evidence and review

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then push the branch and open the PR (the OWNER delegates PR handling): title `feat: SR Linux free live lab with backup/restore (ACR-006)`, body summarising the four success criteria with the evidence lines, ending with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Merge only after CI is green.
