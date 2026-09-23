# scripts/ — gate tooling

| Tool | Job | Exit codes |
|---|---|---|
| `secret_scan.py --root .` | Masked secret scan (locations only, never values) | 0 clean, 1 hit |
| `validate_model.py` | Intended state vs `netbox/schema.yml` | 0 / 1 |
| `render_idempotency.py` | Per-device rerender proof (`--vendor ios\|eos\|srlinux`) | 0 / 1 |
| `ci_gate.py` | Local chain: workflow, scan, validate + render for every vendor, pytest | 0 / 1 |
| `lab_vault.sh` | Creates the encrypted lab login under `~/.netaut` (`make lab-vault`) | 0 / 1 |
| `lab_verify.py` | Live proof on a running lab: readiness wait, drill (restore), deploy, rerun `changed=0` | 0 / 1 |

The gate tools run on plain Python + PyYAML/Jinja2. Ansible-side gates
(syntax-check, dry runs) execute on the Linux CI job. The lab tools run inside
WSL (`make lab-cycle`).
