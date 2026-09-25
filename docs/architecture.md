# ARCH_BASELINE v1 — netaut

## 1. Boundaries and responsibilities
| Component | Owns | Must not own | Contracts |
|---|---|---|---|
| `netbox/` sync | intended-state YAML export, schema | device credentials, rendered configs | schema in `netbox/schema.yml`, export `intended/*.yml` |
| `roles/common/` | NTP/DNS/Syslog vendor-neutral vars | vendor template syntax | role defaults + `tests/` (pytest in `scripts/tests/`) |
| `templates/` | per-vendor Jinja2 render (ios/, eos/, srlinux/) | business logic, facts | render(input intended YAML) -> config text, idempotent |
| `roles/verify/` + `playbooks/deploy/` | pre/post checks, gated deploy, rollback | SoT writes | exit 0 only on real success; FAILED recorded |
| `roles/live_guard/` | live-wave backup, device-state post-check, verified restore (ADR-005) | intended state, render | fails closed per vendor (eos, srlinux) and without a wave id |
| `roles/drift/` + `playbooks/drift/` | read-only facts gather + diff report | any config push | drift report `reports/drift-*.md` |
| CI (`scripts/`, `.github/`) | lint/render/test/dry-run gates | secrets | green gate required before merge |

Dependencies point one way: playbooks -> roles -> templates; nothing depends
back on playbooks. No global mutable state except SoT export.

## 2. State/data model and contracts
Intended state (INV-002 side A): device, interface, prefix, VLAN, VRF, site;
owned by NetBox, cached as YAML, versioned in Git. Operational state (side B):
facts gathered read-only from devices, never written back silently.
Consistency rule: render is a pure function of intended state; same input ->
byte-identical output (REQ-005). Breaking contract changes follow
`docs/orchestration/change-requests/` (ACR).

## 3. Security and threat assessment
| Boundary / surface | Asset | Threat / abuse | Mitigation | REQ/INV/RISK |
|---|---|---|---|---|
| Git repo, CI logs, artifacts | device/admin credentials | secret committed or printed | Vault-only, `no_log: true`, secret scan in CI, masked vars | INV-001, RISK-002 |
| Jinja2 render | device config integrity | injection via SoT string breaks CLI | schema validation + render diff review, fail closed | INV-004, RISK-001 |
| pre-check gate | overlapping IP/VLAN | silent overwrite | conflict check aborts before SSH | REQ-003, RISK-001 |
| deploy play | running network | partial wave, half-applied change | per-wave post-check, stop + rollback | REQ-004, OPS-001 |
| drift job | operational facts | accidental push from drift | read-only credentials, no write tasks in drift role | REQ-006 |

Lab image: SR Linux 26.7.2 and `nokia.srlinux` 1.1.1 pinned and proven live
(ADR-007). No NetBox API client: the repo reads versioned YAML exports (ASM-004).
Live backups hold hashed device secrets: kept under `~/.netaut` (0600), never
in the repo or logs (`no_log`), compare output prints names only (INV-001).

## 4. Failure and reliability analysis
| Failure | Detection | Behavior | Recovery |
|---|---|---|---|
| IP/VLAN conflict | pre-check script | abort, exit 1, zero SSH | fix SoT, rerun |
| post-check fail | post-check play | stop wave, mark FAILED | automatic rollback play, audit record |
| unreachable device | ansible timeout | task FAILED, bounded retry x2 | operator investigates, no silent success |
| rerun same change | config diff empty | report no-change, exit 0 | none needed (REQ-005) |
| corrupted SoT cache | schema validation | fail before render | re-export from NetBox |

Error model: expected (conflict, unreachable) vs defect (template bug) vs
fatal (secret missing -> fail closed, no retry). `max_attempts: 2` in state.

## 5. Performance, observability, configuration, operations
No perf requirement beyond lab scale (tens of devices). Observability: deploy
log + Git audit record (commit, requester, diff, result) per REQ-007; drift
report per run. Config vs secrets vs state strictly separated: `inventories/`
+ `group_vars/` (config), Vault (secrets), `netbox/` cache (state).
Operations: staged lab deploy, exercised rollback each phase gate (OPS-001).

## 6. Technology and dependencies
NetBox (SoT), Ansible + Jinja2 (render/deploy), Containerlab + Nokia SR Linux
(default lab, ADR-007) or Arista cEOS (optional, ADR-006),
Python validation scripts, GitHub Actions CI. ADRs in `docs/decisions/`.
New dependencies need SBOM-equivalent note (collection versions pinned in
`requirements.yml`) at HIGH tier.

## 7. Repository organization
`netbox/`, `inventories/`, `roles/`, `templates/`, `playbooks/`,
`scripts/`, `.github/`, `docs/`, `reports/`. Task ownership prefixes mirror
this layout (see task specs).

## 8. Review before freezing
Checked: no circular deps, no global state, no silent failure (fail closed),
no prod blast radius (lab-only ASM-001), MIT license (ASM-003).
Limits: routing is static + policy only
(ACR-004) and render-only in live waves; OSPF/BGP excluded.
