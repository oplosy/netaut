# Wave runbook

How to execute a change wave: device-less preview first (sections 1-2), then
the live SR Linux lab (section 3, ACR-006).

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

## 3. Live wave (SR Linux lab, ACR-006; cEOS optional)

From WSL, with the lab up (`make lab-up`; cEOS: `make lab-up LAB=eos CEOS_IMAGE=ceos:<ver>`)
and the vault created (`make lab-vault`):

```bash
ANSIBLE_ROLES_PATH=roles ansible-playbook playbooks/deploy/site.yml \
  -i inventories/lab-srlinux.yml -e netaut_mode=live -e netaut_wave=W-<id> \
  -e @~/.netaut/lab-vault-srlinux.yml --vault-password-file ~/.netaut/vault_pass
```

Order per host:
1. Pre-wave backup to `~/.netaut/backups/<host>-<wave>.<ext>` (`json` on SR Linux, `cfg` on EOS).
2. Config roles.
3. Post-check: running-config → snapshot → drift, which must return rc 0.

If the post-check fails, the wave stops. `rollback.yml` replaces the config with
the backup and verifies that the device equals it ("restore verified"), then
records FAILED. IOS in live mode fails closed (no restore path).
For the full live proof, run `make lab-cycle` (fresh lab, drill first, lab torn down
afterwards). Never re-run a FAILED wave unchanged: diagnose, fix intended state
or code, open an ACR if the baseline must move.

## 4. Record

Write `reports/<TASK>.txt` (commands + outputs + deviations), update
`docs/orchestration/state.yaml` as ORCHESTRATOR, commit, push.
