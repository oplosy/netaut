# roles/drift — read-only drift detection

Compares an operational snapshot (side B) against intended state (side A)
and writes a markdown report. Detection only: no push task exists in this
path by design (REQ-006).

- Tool: `files/drift.py --intended … --operational … --report …`
  (exit 0 clean, 2 drift, 1 error). Inputs provably untouched (hash test).
- `--device NAME` compares one host only (live per-host post-check, T-010).
- Side-B shape: `playbooks/drift/operational-schema.yml` (INV-002).
- Fixtures: `playbooks/drift/snapshots/{clean,drifted}.json`.
- Tests: `pytest roles/drift/tests/ -q`.
