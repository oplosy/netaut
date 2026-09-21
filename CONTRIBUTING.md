# Contributing

## One rule

Every change proves itself: green `ci_gate`, green `pi_check all` (when
orchestration files change), and a completion report under `reports/` for
task-sized work.

## Workflow

1. Pick the next READY task from `docs/orchestration/state.yaml`.
2. Stay inside the task `owns`; cross-boundary fixes need an ACR in
   `docs/orchestration/change-requests/`.
3. Verify with the task `verify` commands; executor claims are not evidence.
4. HIGH tasks need independent review in `reports/reviews/` before DONE.
5. Small hygiene commits (docs, lint config) go direct with clear messages.

## Never

- Commit secrets, vault material, or live device addresses.
- Weaken a gate to make it pass.
- Rewrite DONE history; supersede via ACR instead.
