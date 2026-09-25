# netaut - project definition (tier HIGH)

Network automation that makes change repeatable and auditable: intended-state
source of truth, vendor-neutral rendering, gated deploy with rollback, drift
detection. Requirements and invariants live in `registry.yaml`; this file
references IDs and does not restate them.

## Understanding
Owner automates lab network device config (NTP/DNS/Syslog, VLAN/interface)
and wants the same change to be safe to re-run, blocked on conflict before
touching devices, and fully traceable. ACR-003 dropped live execution (no
licensed IOSv image); ACR-005 and ACR-006 brought it back on a free lab.
Live waves run on Nokia SR Linux (ADR-007, proven 2026-09-23); cEOS code is
kept but its live run was cancelled (ACR-007). Proof is CI (device-less)
plus local live-lab evidence under `reports/`. Users: owner (operator) + CI (executor).
Distribution: MIT license, lab-only operation (ASM-001, ASM-003).

## Risk tier
HIGH. Rationale in `registry.yaml` (tier_rationale). Re-tier to CRITICAL if
production devices or customer traffic enter scope; re-tier down only with
recorded owner risk acceptance.

## Scope and non-goals
In scope: REQ-001..REQ-009. REQ-008 covers static routes and prefix-list/
route-map policy only (ACR-004), render-only in waves. Non-goals: OSPF/BGP,
physical cabling, NetBox hosting itself, production rollout.

## Parked ideas (not tasks)
pyATS full testbed, Oxidized backup integration, ChatOps trigger.

## Architecture (baseline v1)
Summary only; authority is `docs/architecture.md` (`ARCH_BASELINE v1`).
NetBox export -> validated intended-state YAML -> Jinja2 vendor render (IOS,
EOS, SR Linux) -> pre-check gate -> Ansible deploy (live: pre-wave backup) ->
post-check gate (live: device state vs intended via drift) -> rollback on
failure (live: verified restore) -> Git audit record. Drift job compares device-read operational state against
intended state read-only.

## Decisions
| ID | Decision | Reason | Rollback cost |
|----|----------|--------|---------------|
| ADR-001 | NetBox as source of truth, YAML export cache in repo | Single write source; cache keeps CI hermetic | Medium: sync code changes |
| ADR-002 | Ansible + Jinja2 render, vendor templates isolated under templates/ | Team skill fit; INV-003 separation | Medium: role/template rewrite |
| ADR-003 | Ansible Vault for secrets, CI masking, no secrets in artifacts | INV-001; RISK-002 | Low: re-key and purge history |
| ADR-004 | Containerlab + IOSv lab first (DEPRECATED, ACR-003) | Cheap reversible blast radius | n/a |
| ADR-005 | Pre-wave backup enabling live restore | Rollback must undo, not just mark FAILED | Low: live_guard role |
| ADR-006 | Containerlab + Arista cEOS lab (optional since ACR-006) | Free, close to IOS syntax | Low: lab files + eos task files |
| ADR-007 | Containerlab + Nokia SR Linux lab (default) | Public image, no account | Low: lab files + srlinux task files |

## Failure behavior
Conflict in pre-check: abort before SSH, exit non-zero, no diff applied
(REQ-003). Post-check failure: stop wave, run rollback play, record FAILED
result (REQ-004). Invalid critical config: schema validation fails the run
before render (INV-004).

## Verification and release
CI on every push: yamllint, secret scan, model validation, render
idempotency, pytest suites, ansible-playbook --syntax-check, EOS argspec proof,
dry-run --check per inventory (OPS-002). ansible-lint is not run.
Live proof runs locally (`make lab-cycle`) and is committed under `reports/`.
Release: manual tag; lab deploy staged with exercised rollback (OPS-001).
Definition of done per task: all `verify` commands pass on orchestrator rerun.
