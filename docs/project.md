# netaut - project definition (tier HIGH)

Network automation that makes change repeatable and auditable: intended-state
source of truth, vendor-neutral rendering, gated deploy with rollback, drift
detection. Requirements and invariants live in `registry.yaml`; this file
references IDs and does not restate them.

## Understanding
Owner automates lab network device config (NTP/DNS/Syslog, VLAN/interface)
and wants the same change to be safe to re-run, blocked on conflict before
touching devices, and fully traceable. Live device execution is out of scope
per ACR-003 (no licensed image); proof is CI + dry-run + drill against
fixtures. Users: owner (operator) + CI (executor).
Distribution: private repo, lab-only operation (ASM-001, ASM-003).

## Risk tier
HIGH. Rationale in `registry.yaml` (tier_rationale). Re-tier to CRITICAL if
production devices or customer traffic enter scope; re-tier down only with
recorded owner risk acceptance.

## Scope and non-goals
In scope: REQ-001..REQ-007. Non-goals: routing policy (REQ-008, DEFERRED),
physical cabling, NetBox hosting itself, production rollout.

## Parked ideas (not tasks)
pyATS full testbed, Oxidized backup integration, ChatOps trigger.

## Architecture (baseline v1)
Summary only; authority is `docs/architecture.md` (`ARCH_BASELINE v1`).
NetBox export -> validated intended-state YAML -> Jinja2 vendor render (IOS) ->
pre-check gate -> Ansible deploy -> post-check gate -> rollback on failure ->
Git audit record. Drift job compares device-read operational state against
intended state read-only.

## Decisions
| ID | Decision | Reason | Rollback cost |
|----|----------|--------|---------------|
| ADR-001 | NetBox as source of truth, YAML export cache in repo | Single write source; cache keeps CI hermetic | Medium: sync code changes |
| ADR-002 | Ansible + Jinja2 render, vendor templates isolated under templates/ | Team skill fit; INV-003 separation | Medium: role/template rewrite |
| ADR-003 | Ansible Vault for secrets, CI masking, no secrets in artifacts | INV-001; RISK-002 | Low: re-key and purge history |
| ADR-004 | Containerlab + IOSv lab first | Cheap reversible blast radius | Low: new inventory plugin |

## Failure behavior
Conflict in pre-check: abort before SSH, exit non-zero, no diff applied
(REQ-003). Post-check failure: stop wave, run rollback play, record FAILED
result (REQ-004). Invalid critical config: schema validation fails the run
before render (INV-004).

## Verification and release
CI on every push: yamllint, ansible-lint, ansible-playbook --syntax-check,
model validation script, render diff test, dry-run --check (OPS-002).
Release: manual tag; lab deploy staged with exercised rollback (OPS-001).
Definition of done per task: all `verify` commands pass on orchestrator rerun.
