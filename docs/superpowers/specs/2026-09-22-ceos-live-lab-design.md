# Design: free live lab on Arista cEOS

Date: 2026-09-22. Status: approved by OWNER in chat. Baseline: v1.

## Goal
Close the biggest gap: netaut has never touched a device. Run real waves
against a free, legal lab while keeping every existing device-less gate.

Success means all of the following on a local cEOS lab, with evidence in `reports/`:
1. A live wave applies intended state to 2 cEOS nodes.
2. The post-check compares real device state with intended state and passes.
3. A rerun reports `changed=0`.
4. A forced post-check failure restores the pre-wave backup (ADR-005). A
   drift check afterwards confirms the device matches the backup again.

## Decisions
- **Device OS: Arista cEOS-lab.** It is free (needs a free Arista account;
  the OWNER downloads the image) and its syntax is close to IOS. Containerlab
  and `arista.eos` support it natively. This respects ACR-003's no-pay decision.
  Rejected alternatives: SR Linux (render rewrite), FRR (no VLAN/switchport),
  and IOL via CML-Free (licence ambiguity).
- **Vendor support: per-vendor dispatch inside each role.** `main.yml` keeps
  the fail-closed asserts and runs `include_tasks: "{{ ansible_network_os }}.yml"`.
  `ios.yml` and `eos.yml` hold only module calls. This preserves INV-003
  (no CLI strings in roles; vendor differences live in modules and
  `templates/<vendor>/`). Rejected alternatives: full-config template push
  (loses resource-module idempotency) and `cli_config` only (worst diffs).
- **CI stays device-less.** The cEOS image may not be redistributed, so CI cannot
  run it. Live checks run locally via `make lab-verify`, and their output
  is committed as evidence.

## Components

### Lab (`lab/`)
- `lab/netaut.clab.yml`: 2 cEOS nodes (`lab-sw01`, `lab-sw02`) with an
  `Ethernet1` link between them on the containerlab default management
  network. The image tag is a variable; the image is never committed.
- `inventories/lab-eos.yml`: `ansible_network_os: arista.eos.eos`,
  `network_cli`. Credentials come from Vault (`vault_lab_user`,
  `vault_lab_password`), and the vault file stays gitignored (INV-001, ACR-002).
  `inventories/lab.yml` (IOS) stays unchanged as the device-less reference.
- Makefile targets `lab-up`, `lab-down` and `lab-verify` call containerlab
  and Ansible through WSL.

### Model and render
- `netbox/schema.yml`: `platform_allowed: [ios, eos]`.
- `netbox/intended/lab-eos.yml`: the same intent as `sample.yml`, with
  `platform: eos` and interface names `Ethernet1`.
- `templates/eos/`: EOS twins of every IOS template (`vlan_interface.j2`,
  `routing/static.j2`).
- `scripts/render_idempotency.py`: renders every template for the vendor,
  not only `vlan_interface.j2`. CI runs it for `ios` and `eos`.

### Deploy wave (`playbooks/deploy/`)
- The play targets the `lab` group instead of `ios`.
- **Pre-wave backup (ADR-005, now accepted).** In live mode, before any
  change, the play saves each host's `running-config` to
  `reports/backups/<host>-<wave>.cfg`. That path is gitignored. Logs mask
  credentials (`no_log` on tasks that carry them).
- **Real post-check.** In live mode the play gathers facts, writes an
  operational snapshot in the `playbooks/drift/operational-schema.yml`
  shape, and runs the existing drift tool against the intended state.
  Only rc 0 passes; rc 2 (drift) or rc 1 (tool error) fails the wave. The drill
  flag `netaut_force_postcheck_fail` stays. In render-only mode the
  post-check keeps its current behaviour.
- **Live rollback.** Restore the backup with a config replace
  (`configure replace` via `arista.eos.eos_config`), then run a drift check against
  the backup-derived snapshot. The fail-closed assert in `rollback.yml`
  is removed only for platforms that have a restore implementation. Any
  other platform in live mode still fails closed.

### Scope of the live wave
The wave covers the same things `site.yml` covers today: common (NTP/DNS/
Syslog) plus VLAN/interfaces. Post-check coverage matches what the drift
tool compares, which is the same set. Routing (T-007) stays render-only.
Adding it to the live wave and to the operational schema is a later task,
recorded as a known gap and not done silently.

## Error handling
- Conflict gate stays first: a conflict aborts with zero connections.
- If the backup is missing or empty, the wave does not start (fail closed).
- If restore fails, the wave is recorded as FAILED with the restore error.
  There is no retry loop and the operator gets the host name and backup path.
- If the lab is not running, `lab-verify` fails fast on an
  unreachable host before any change.

## Testing
- **CI (device-less):** yamllint, secret scan, schema validation of both
  intended files, render idempotency for ios and eos, unit tests for the
  snapshot builder (facts JSON fixture to operational-schema shape) and
  for the vendor dispatch (a missing `<os>.yml` fails closed).
- **Local live (`make lab-verify`):** deploy, then rerun `changed=0`, then drift=0,
  then a forced post-check fail with restore and drift=0 against the backup.

## Orchestration records
- **ACR-005:** re-opens live scope on free cEOS. It supersedes ACR-003 decision
  1 only. ACR-003's "no pay" rule stays.
- **ADR-006:** cEOS containerlab lab. It replaces the deprecated ADR-004.
- **ADR-005:** status moves from proposed to accepted.
- Tasks:
  - **T-008:** vendor dispatch in roles plus EOS render. Device-less, CI only.
  - **T-009:** lab bring-up (containerlab, inventory, Make targets).
    Blocked on the OWNER providing the image and a working Docker Desktop.
  - **T-010:** live wave plus real post-check.
  - **T-011:** backup and restore. HIGH risk, needs `reports/reviews/T-011.md`.

## Out of scope
OSPF/BGP, live IOS, running the lab in CI, and routing in the live wave (see above).

## OWNER prerequisites
1. Create a free arista.com account and download `cEOS64-lab-<version>.tar.xz`.
2. Fix Docker Desktop (it currently fails to start). WSL Ubuntu already works.
