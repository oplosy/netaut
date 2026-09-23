# Design: free live lab on Nokia SR Linux

Date: 2026-09-23. Status: approved by OWNER in chat. Baseline: v1.
Follows `2026-09-22-ceos-live-lab-design.md`; that design stays valid for EOS.

## Why this exists
The cEOS lab (ACR-005, T-009..T-011) is blocked: Arista registration rejects
personal e-mail (Gmail) and the OWNER has no corporate address. Unofficial
cEOS images are rejected (licence, untrusted source). Nokia SR Linux is
published openly at `ghcr.io/nokia/srlinux` with no registration, so it
unblocks live execution while respecting ACR-003's no-pay rule.

## Goal
Unchanged from the cEOS design. Success means all of the following on a
local SR Linux lab, with evidence in `reports/`:
1. A live wave applies intended state (NTP/DNS/syslog, VLAN/access port) to
   2 SR Linux nodes.
2. The post-check compares real device state with intended state and passes.
3. A rerun reports `changed=0`.
4. A forced post-check failure restores the pre-wave backup (ADR-005). A
   check afterwards confirms the device matches the backup again.

## Decisions
- **EOS stays; SR Linux is a third vendor.** EOS render, dispatch and argspec
  proof keep running in CI at no cost, and the cEOS lab can be brought up
  later if a corporate Arista account appears. Rejected: removing EOS
  (throws away tested code for no gain).
- **Transport: `nokia.srlinux` collection over JSON-RPC (httpapi).**
  `nokia.srlinux.config` does path-based `update`/`replace`/`delete`, honours
  check mode, and computes `changed` from a device-side diff, so idempotency
  (criterion 3) comes for free. `nokia.srlinux.get` returns structured JSON,
  so the post-check needs no text parsing. Containerlab enables JSON-RPC on
  SR Linux nodes by default. Rejected: `network_cli` with raw CLI (no cliconf
  plugin, hand-written idempotency, poor diffs) and gNMI via `gnmic` +
  `command` (leaves Ansible, hand-written `changed`).
- **CI stays device-less for live checks.** The SR Linux image is public, so
  a CI live job is possible, but it is out of scope for now (OWNER decision).

## Components

### Lab
- `lab/netaut-srl.clab.yml`: 2 nodes `lab-sw01`/`lab-sw02`, kind
  `nokia_srlinux`, image `ghcr.io/nokia/srlinux:<pinned>` (pin chosen in the
  plan and recorded in every live report), link `ethernet-1/1` <->
  `ethernet-1/1`, mgmt network `netaut-srl-mgmt` on `172.20.21.0/24`
  (`.11`/`.12`) so it never collides with the cEOS lab on `172.20.20.0/24`.
- `lab/netaut.clab.yml` (cEOS) is untouched.
- Makefile: `LAB ?= srl`; `lab-up`, `lab-down`, `lab-verify` pick the
  topology and inventory from `LAB` (`srl` or `eos`).

### Inventory
- `inventories/lab-srl.yml`: group `srl` under `lab`,
  `ansible_connection: ansible.netcommon.httpapi`,
  `ansible_network_os: nokia.srlinux.srlinux`, `ansible_httpapi_use_ssl: true`,
  `ansible_httpapi_validate_certs: false`. The certificate check is off
  because containerlab issues a self-signed lab certificate; this is a
  lab-only exception recorded in ADR-007. Login from the vault
  (`vault_lab_user`/`vault_lab_password`, INV-001),
  `netaut_intended_file` points at `netbox/intended/lab-srl.yml`.

### Model
- `netbox/schema.yml`: `platform_allowed: [ios, eos, srl]`.
- `netbox/intended/lab-srl.yml`: same intent as `lab-eos.yml`, with
  `platform: srl` and interface `ethernet-1/1`.

### Intended state -> SR Linux mapping

| Intended | SR Linux |
|---|---|
| VLAN `99` name `MGMT` | `network-instance vlan-99`, `type mac-vrf`, `description MGMT` |
| access port `ethernet-1/1`, vlan 99, description | `interface ethernet-1/1` (`admin-state enable`, description), `subinterface 0` `type bridged` with `vlan encap untagged`; `ethernet-1/1.0` is an interface of `vlan-99` |
| NTP servers | `/system/ntp`: `admin-state enable`, `network-instance mgmt`, `server <ip>` |
| DNS servers | `/system/dns`: `network-instance mgmt`, `server-list [<ip>...]` |
| Syslog hosts | `/system/logging`: `network-instance mgmt`, `remote-server <ip>` |

Mac-vrf names are derived from the VLAN id (`vlan-<id>`), not the VLAN name,
so they never collide with the built-in `mgmt` instance. The VLAN name
becomes the description.

### Roles
- `common/tasks/srl.yml` and `vlan_interface/tasks/srl.yml`: only
  `nokia.srlinux.config` calls with `update`, `save_when: never` (INV-003).
- The supported-vendor asserts in `common`, `vlan_interface` and
  `live_guard` gain `srl`. `routing` stays render-only (no `srl.yml`); its
  fail-closed assert is unchanged.

### `live_guard`
- `tasks/srl/backup.yml`: `nokia.srlinux.get` of `/` from the `running`
  datastore, written as JSON to `~/.netaut/backups/<host>-<wave>.json`
  (mode 0600). The backup/restore file extension becomes per-vendor
  (`cfg` for eos, `json` for srl); `backup.yml` and `restore.yml` keep their
  vendor-neutral fail-closed checks.
- `tasks/srl/fetch.yml`: `get` of the five wave paths (`/system/ntp`,
  `/system/dns`, `/system/logging`, `/interface`, `/network-instance`),
  stored locally as JSON.
- `tasks/srl/restore.yml`: `nokia.srlinux.config` with `replace` of `/`
  using the backup JSON.
- `files/srl_snapshot.py`: stdlib-only; SR Linux JSON -> operational
  snapshot in the `playbooks/drift/operational-schema.yml` shape;
  `--compare` for the restore proof. Same exit codes as `eos_snapshot.py`
  (0 ok/equal, 2 differences, 1 error).

### Render
- `templates/srl/vlan_interface.j2` and `templates/srl/routing/static.j2`
  emit SR Linux flat `set / ...` lines. They serve preview and the
  render-idempotency test only; waves use the modules.

## Wave flow
`playbooks/deploy/site.yml` does not change; the vendor lives in
`live_guard` and the role `srl.yml` files.

1. **Backup.** Same rules as EOS: an existing backup for the wave id or an
   empty/missing backup stops the wave before the first config task. The
   backup carries the admin user's hashed password, so it never enters the
   repo and its content is never printed.
2. **Apply.** `update` calls; the device diff makes a rerun `changed=0`.
   `save_when: never`: the lab is ephemeral and the backup file is the
   source of truth.
3. **Post-check.** Fetch the five paths, build the snapshot, run
   `drift.py --fail-on-drift`. Only rc 0 passes. Parser rules: only
   network-instances named `vlan-<id>` with `type mac-vrf` are reported as
   VLANs; an access port is a `bridged` subinterface with `untagged`
   encapsulation that is attached to a `vlan-<id>` mac-vrf; addresses keep
   IP tokens only.
4. **Restore (rescue).** `replace /` with the backup JSON.
5. **Restore proof.** Read `/` again; `srl_snapshot.py --compare` checks the
   parsed fields and the whole canonicalised JSON (sorted keys), so a
   difference anywhere fails with rc 2. Output lists field names and
   difference counts only, never config content.

Fail closed: IOS still has no live implementation; no wave id, no live wave.

## Risk to prove first
The collection docs do not state that `replace` accepts the root path `/`.
The first plan step proves it on the lab (backup `/`, change something,
`replace /`, compare). If root replace is rejected, backup, restore and the
restore proof narrow to the five wave paths above, and the proof covers
those paths in full. The plan records which variant was taken.

## Error handling
- Conflict gate stays first: a conflict aborts with zero connections.
- Missing/empty backup: the wave does not start.
- Restore failure: the wave is FAILED with the restore error, host name and
  backup path; no retry loop.
- Lab not running: `lab-verify` fails fast on an unreachable host before
  any change.
- A JSON-RPC commit that fails is rolled back by the device (the module's
  transaction), and the play then goes to rescue.

## Testing
- **CI (device-less, every push):** schema validation of `lab-srl.yml`;
  `render_idempotency.py --vendor srl`; pytest `test_srl_snapshot.py`
  (fixtures captured from real SR Linux JSON: clean, drifted, restore
  compare) and `test_render_srl.py`; role-dispatch and live_guard contract
  tests extended to `srl`; `site.yml --check` with `inventories/lab-srl.yml`
  in render-only mode (no device connection).
- **No device-less argspec proof for srl.** `nokia.srlinux.config` has no
  `rendered` state; module arguments are proven by the live lab.
- **Local live (`make lab-verify LAB=srl`):** one step per success criterion;
  output committed to `reports/T-0xx.txt` with the image version.

## Dependencies
- `requirements.yml`: add `nokia.srlinux`, version verified on Galaxy and
  pinned during planning.

## Orchestration records
- **ACR-006:** live lab moves to SR Linux; cEOS stays optional (needs a
  corporate Arista account). ACR-003's no-pay rule stays.
- **ADR-007:** SR Linux containerlab lab is the default lab. ADR-006 stays
  accepted for EOS but is no longer the default; its "SR Linux rejected"
  line gets a note pointing to ADR-007 and why the trade-off changed.
- **REQ-009:** text generalised to "a free lab" (SR Linux default, cEOS
  optional).
- Tasks (mirroring T-008..T-011):
  - **T-012:** SR Linux model, render, role dispatch; root-replace proof first.
  - **T-013:** SR Linux lab bring-up (topology, inventory, Make targets).
  - **T-014:** live wave plus real post-check.
  - **T-015:** backup and restore. HIGH risk, needs `reports/reviews/T-015.md`.
- **T-009..T-011:** stay BLOCKED; `blocked_on` becomes "OWNER corporate
  Arista account (optional)".

## Out of scope
Live tests in CI, routing in the live wave, OSPF/BGP, live IOS, removing EOS.

## OWNER prerequisites
None. The image is pulled from `ghcr.io` without an account.
