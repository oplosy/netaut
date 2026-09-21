# Security policy

Private lab-automation repo. No production devices in scope (ASM-001).

## Rules (INV-001)

- Secrets live in Vault / CI secrets only. Never in Git, logs, or artifacts.
- `scripts/secret_scan.py` runs on every push and blocks on hits.
- Credential tasks use `no_log: true`; CI variables are masked.

## Reporting

Found a leaked secret or a bypass of the gates? Open a private issue or
contact the repo owner directly. Rotate the exposed credential first,
purge history second, then report.
