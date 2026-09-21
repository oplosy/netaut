# netbox/ — intended-state source of truth

`schema.yml` is the contract (v1): sites, vrfs, vlans, prefixes, devices,
plus optional static-routing sections. `intended/` holds versioned YAML
exports of NetBox for hermetic CI (ADR-001).

Rules: desired state only (INV-002, no operational facts), no secrets
(INV-001). Validate with `scripts/validate_model.py`; policy sections with
the routing `policy_check`.
