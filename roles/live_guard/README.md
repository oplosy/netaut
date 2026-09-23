# live_guard

Live-wave safety steps (T-010, T-011, T-014, T-015, ADR-005). The deploy wave calls this role only
when `netaut_mode: live`. Render-only runs and CI never reach it.

| Entry point | When | Does |
|---|---|---|
| `tasks_from: backup` | first task of the wave | saves running-config, fails closed if missing/empty |
| `tasks_from: postcheck` | after config tasks | running-config → snapshot → `drift.py --device --fail-on-drift` |
| `tasks_from: restore` | wave rescue | config replace from backup, then `--compare` backup vs restored |

## Fail-closed rules
- Every entry point first asserts a supported vendor (`eos`, `srlinux`) and a
  non-empty `netaut_wave`. IOS in live mode stops here; it is never skipped silently.
- If the backup never happened, restore reports "no change made" instead of
  restoring from a missing file.
- The post-check only passes when drift returns rc 0.

## Files outside the repo
Backups and fetched configs contain the device's hashed user secrets
(INV-001). They are written to `~/.netaut/backups/<host>-<wave>.<ext>` and
`~/.netaut/runs/<wave>/` with mode 0600/0700, never under the repo.
`<ext>` is `live_guard_ext`: `cfg` for eos, `json` for srlinux.

## Vendors
- `eos/` (T-010/T-011): `eos_config` backup, `configure replace` restore, `eos_snapshot.py`.
- `srlinux/` (T-014/T-015): `get /` backup as JSON, `replace /` restore, `srlinux_snapshot.py`
  post-check and restore proof. Every task that touches the datastore is `no_log`.

## Adding a vendor
Create `tasks/<vendor>/{backup,fetch,restore}.yml` and `files/<vendor>_snapshot.py`,
then add the vendor to the entry-point asserts. `scripts/tests/test_live_guard_contract.py`
checks that every vendor directory implements all three actions.

Tests: `pytest roles/live_guard scripts/tests/test_live_guard_contract.py -q`.
