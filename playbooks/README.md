# playbooks/ — gated waves

- `deploy/site.yml` — pre-check gate on localhost, then block/rescue/always
  wave: roles apply (live only), post-check asserts, rescue runs
  `rollback.yml` and records FAILED. Default `render-only` is device-less.
- `drift/report.yml` — detection only, zero push tasks. Report defaults to
  `/tmp/netaut-drift-report.md`; fixtures under `snapshots/`.

Always preview first: `--check --diff` (deploy), `--check` (drift).
See `docs/runbook.md`.
