# roles/verify — offline conflict gate

Fail-closed pre-deploy checks (REQ-003). Local files only: the tool imports
stdlib + PyYAML and nothing else, so it cannot open device connections
(proven by test).

- Tool: `files/precheck.py --input <intended.yml>` (exit 0 clean, 1 conflict).
- Catches: duplicate names, unknown vlan/vrf/site refs, range violations,
  overlapping prefixes.
- Role wrapper runs on localhost, `run_once`, `check_mode: false` so dry
  runs prove the wiring instead of skipping it.
- Tests: `pytest roles/verify/tests/ -q`.
