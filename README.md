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
| `netbox/` | Intended-state schema + `intended/sample.yml` (ios), `intended/lab-eos.yml` (eos) |
| `inventories/` | `lab.yml` (ios, device-less), `lab-eos.yml` (cEOS lab); credentials via Vault only |
| `lab/` | Containerlab topology: 2x Arista cEOS (ADR-006) |
| `roles/common/` | NTP / DNS / Syslog (phase 1, low risk) |
| `roles/vlan_interface/` | VLAN + access interfaces (phase 2) |
| `templates/{ios,eos}/` | Raw vendor render (logic stays in roles) |
| `roles/*/tasks/{ios,eos}.yml` | Vendor module calls; `main.yml` keeps asserts + dispatch |
| `roles/live_guard/` | Live only: pre-wave backup, device-state post-check, verified restore |
| `roles/verify/` | Offline conflict gate (no network imports by design) |
| `playbooks/deploy/` | Gated wave: pre-check → block/rescue/always → rollback |
| `playbooks/drift/` | Read-only drift report + side-B schema + fixtures |
| `scripts/` | `secret_scan`, `validate_model`, `render_idempotency`, `ci_gate`, `lab_verify`, `lab_vault.sh` |
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

## Live lab (cEOS, free)

Live execution is back in scope on free Arista cEOS (ACR-005). Run it from WSL:

```bash
docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>   # image from a free arista.com account
make lab-up CEOS_IMAGE=ceos:<ver>
make lab-vault      # encrypted login under ~/.netaut, never in the repo
make lab-verify     # drill (restore) -> deploy -> rerun changed=0
make lab-down
```

A live wave is `-e netaut_mode=live -e netaut_wave=<id>`. It takes a backup
first, post-checks real device state against intended state through the
drift tool, and restores the backup when the post-check fails. IOS stays
render-only: live mode fails closed there.
**Status:** the live path is built and tested device-less; the live evidence
(T-009..T-011) is pending the cEOS image import.

## Proof it works

- Idempotent: every template of each vendor renders byte-identical output (`scripts/render_idempotency.py`).
- Pre-check aborts on seeded IP/VLAN conflicts with zero connections opened.
- Forced post-check failure stops the wave, runs rollback, records FAILED (drilled).
- Drift fixtures detected with read-only inputs (hashes untouched).
- Module argument specs proven device-less (`playbooks/proof/rendered.yml`, eos in CI).
- Live mode fails closed without a wave id or for vendors without a restore path.
- Role and gate test suites green (`make test`); hosted CI green; `pi_check all` green (12/12 gates, HIGH tier).

See `docs/architecture.md` (ARCH_BASELINE v1), `docs/decisions/`,
`reports/T-000.txt` … `reports/T-008.txt` (no T-006: dropped by ACR-003), and `docs/orchestration/`.

## Scope phases

1. NTP / DNS / Syslog (done) → 2. VLAN / interface (done) → 3. Static routing + policy (done, REQ-008; OSPF/BGP excluded)
→ 4. EOS vendor (done, T-008) → 5. Live cEOS lab with backup/restore (built; live run pending image, T-009..T-011).
