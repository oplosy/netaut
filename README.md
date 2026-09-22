# netaut

[![netaut-gates](https://github.com/oplosy/netaut/actions/workflows/ci.yml/badge.svg)](https://github.com/oplosy/netaut/actions/workflows/ci.yml)

Repeatable, reviewable network change: intended-state source of truth,
vendor-neutral rendering, gated deploy with rollback, drift detection.
Every change is re-runnable, blocked on conflict before touching devices,
and traceable via Git.

## How it works

NetBox export → validated intended-state YAML → Jinja2 vendor render →
pre-check gate → Ansible deploy → post-check gate → rollback on failure →
Git audit record. A read-only drift job compares device facts against
intended state. Reruns produce byte-identical output (no noise).

## Layout

| Path | What |
|---|---|
| `netbox/` | Intended-state schema + sample (`intended/`) |
| `inventories/` | Lab inventory (credentials via Vault only, never here) |
| `roles/common/` | NTP / DNS / Syslog (phase 1, low risk) |
| `roles/vlan_interface/` | VLAN + access interfaces (phase 2) |
| `templates/ios/` | Raw IOS render (logic stays in roles) |
| `roles/verify/` | Offline conflict gate (no network imports by design) |
| `playbooks/deploy/` | Gated wave: pre-check → block/rescue/always → rollback |
| `playbooks/drift/` | Read-only drift report + side-B schema + fixtures |
| `scripts/` | `secret_scan`, `validate_model`, `render_idempotency`, `ci_gate` |
| `.github/workflows/` | Merge gates on every push/PR |
| `docs/` | Architecture baseline, decisions, orchestration state |

## Quickstart (lab)

```bash
pip install pyyaml pytest jinja2 ansible-core yamllint
ansible-galaxy collection install -r requirements.yml

# full local gate chain incl. yamllint (must be green before merge)
make gates
# or, without make (no yamllint step):
python scripts/ci_gate.py --sample netbox/intended/sample.yml

# dry runs, no devices touched
ansible-playbook playbooks/deploy/site.yml -i inventories/lab.yml --check --diff
ansible-playbook playbooks/drift/report.yml -i inventories/lab.yml --check
```

Live waves would flip `netaut_mode: live` per wave record with Vault
credentials at runtime (`--vault-password-file`, never committed).
Live execution is currently out of scope (ACR-003: no licensed device image);
everything below is proven device-less.

## Proof it works

- Idempotent: same input renders byte-identical output (`scripts/render_idempotency.py`).
- Pre-check aborts on seeded IP/VLAN conflicts with zero connections opened.
- Forced post-check failure stops the wave, runs rollback, records FAILED (drilled).
- Drift fixtures detected with read-only inputs (hashes untouched).
- Role and gate test suites green (`make test`); hosted CI green; `pi_check all` green (12/12 gates, HIGH tier).

See `docs/architecture.md` (ARCH_BASELINE v1), `docs/decisions/`,
`reports/T-000.txt` … `reports/T-007.txt` (no T-006: dropped by ACR-003), and `docs/orchestration/`.

## Scope phases

1. NTP / DNS / Syslog (done) → 2. VLAN / interface (done) → 3. Static routing + policy (done, REQ-008; OSPF/BGP excluded).
