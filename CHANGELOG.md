# Changelog

Generated from commit history (`git log --oneline`).

## Unreleased

- Review T-015 minors fixed: lab login kept out of output, `lab-cycle` always tears down,
  unknown `LAB=` stops clearly, wave ids unique across vendors, backup parsed before a
  srlinux restore, parser errors print the type only, braces pinned in backup/fetch

## v1.1.0 (2026-09-23)

Live lab release: EOS as a second vendor, SR Linux as a third with the first
live waves (backup, drift post-check, verified restore). Two parts below.

### SR Linux live lab (ACR-006)

- T-012: srlinux platform, preview render, role module calls (nokia.srlinux 1.1.1), JSON snapshot parser
- T-013: containerlab SR Linux topology, httpapi inventory, `LAB=` switch, readiness wait, `make lab-cycle`
- T-014/T-015: live wave, drift post-check, root-replace restore with proof; first live evidence (SR Linux 26.7.2)
- Fix: drift now reports intended interfaces missing on the device (all vendors)
- Review: reports/reviews/T-015.md (1 critical + 4 important fixed, 7 minors deferred)
- Decisions: ACR-006, ADR-007 (cEOS optional)
- Follow-up: `ci_gate.py` covers srlinux; docs synced with the live lab (#7)

### EOS vendor and cEOS live lab (ACR-005; cEOS live run optional)

- T-008: EOS render twins, per-role vendor dispatch, all-template render proof, device-less argspec proof in CI
- T-009..T-011: containerlab cEOS topology, eos inventory, `live_guard` (backup, drift post-check, verified restore), `make lab-*`; live run needs a corporate Arista account (optional)
- Fixes: ios static-route render line join, ios_system argspec, CI yamllint on installed collections,
  intended-state fact never reaching localhost (live waves), ios access mode
- Review: reports/reviews/T-011.md (7 findings, all fixed)
- Decisions: ACR-005, ADR-006, ADR-005 accepted

## v1.0.0 (2026-09-22)

Device-less baseline: everything below.

## Waves (features)

- Baseline v1: risk-calibrated init, HIGH tier, 12/12 gates (`bbc4d4a`)
- T-000: scaffold, lab inventory, audit convention (`1556201`)
- T-001: intended-state model + NTP/DNS/Syslog role (`7d534dc`)
- T-002: VLAN/interface model + isolated vendor render (`bab2677`)
- T-003: pre/deplo/post gates + rollback, reviewed HIGH task (`bf22610`)
- T-004: idempotency proof + read-only drift detection (`2f40670`)
- T-005: CI gates + secret scan + audit evidence (`6070ad7`)
- T-007: static routes + prefix-list/route-map policy (`27bb45a`)

## Scope decisions

- ACR-001: vault default for device-less runs
- ACR-002: no vault filename in committed config
- ACR-003: live-device scope dropped (no licensed image); ADR-004 deprecated
- ACR-004: routing scope active as static + policy (OSPF/BGP excluded)
- ADR-005 (proposed): pre-wave backup for live rollback restore

## Hygiene and docs

- EditorConfig, gitattributes (LF), yamllint, pre-commit hooks
- SECURITY, CONTRIBUTING, wave runbook, repo README
- Role READMEs (common, vlan_interface, verify, drift, routing)
- Area READMEs (templates, netbox, playbooks, scripts)
- GitHub: PR template, CODEOWNERS, Dependabot
- Makefile mirroring CI gates (`84ea6cb`)
