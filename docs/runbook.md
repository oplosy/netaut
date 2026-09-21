# Wave runbook

How to execute a change wave against the lab (when a live lab exists;
currently all runs below are device-less unless noted).

## 1. Prepare

```bash
python scripts/ci_gate.py --sample netbox/intended/sample.yml
```

Everything must be green before touching anything.

## 2. Preview (always first)

```bash
ansible-playbook playbooks/deploy/site.yml -i inventories/lab.yml --check --diff
ansible-playbook playbooks/drift/report.yml -i inventories/lab.yml --check
```

Expected: pre-check OK, live roles skipped in render-only, post-check OK,
drift report NO DRIFT on a clean tree.

## 3. Live wave (requires image-procured lab + Vault)

```bash
ansible-playbook playbooks/deploy/site.yml -i inventories/lab.yml \
  -e netaut_mode=live --vault-password-file <runtime-only-path>
```

Post-check failure stops the wave and runs `rollback.yml`, then records
FAILED. Never re-run a FAILED wave unchanged: diagnose, fix intended state
or code, open an ACR if the baseline must move.

## 4. Record

Write `reports/<TASK>.txt` (commands + outputs + deviations), update
`docs/orchestration/state.yaml` as ORCHESTRATOR, commit, push.
