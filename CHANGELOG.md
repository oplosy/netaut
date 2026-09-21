# Changelog

Generated from commit history (`git log --oneline`). Unreleased: no tags yet.

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
