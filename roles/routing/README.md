# roles/routing — static routes + prefix-list/route-map policy

Phase 3 policy automation (REQ-008, ACR-004). Static routes and
prefix-list/route-map policy only; neighbors, OSPF, BGP excluded.

- Inputs: `netaut_static_routes`, `netaut_prefix_lists`, `netaut_route_maps`.
  Null defaults fail closed.
- Modules only (INV-003): `ios_static_routes`, `ios_prefix_lists`,
  `ios_route_maps` (note singular `route_map:` key), merged per entry.
- Policy gate: `files/policy_check.py` enforces INV-005 (every route-map
  prefix-list reference resolves); exit 0/1.
- Raw twin: `templates/ios/routing/static.j2`.
- Tests: `pytest roles/routing/tests/ -q` (rerender, content, policy).
