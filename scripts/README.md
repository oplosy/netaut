# scripts/ — gate tooling

| Tool | Job | Exit codes |
|---|---|---|
| `secret_scan.py --root .` | Masked secret scan (locations only, never values) | 0 clean, 1 hit |
| `validate_model.py` | Intended state vs `netbox/schema.yml` | 0 / 1 |
| `render_idempotency.py` | Per-device rerender proof (`--vendor ios`) | 0 / 1 |
| `ci_gate.py` | Local chain: workflow, scan, validate, idempotency, pytest | 0 / 1 |

All run on plain Python + PyYAML/Jinja2. Ansible-side gates (syntax-check,
dry runs) execute on the Linux CI job and were proven via WSL during waves.
