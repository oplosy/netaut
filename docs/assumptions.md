# Assumptions and owner decisions

Categories: PRODUCT | LEGAL | RISK | COMMERCIAL | TECHNICAL.
Statuses: ASSUMED | OWNER_DECISION_REQUIRED | CONFIRMED | REJECTED | EXTERNALLY_BLOCKED.
`Blocks` is YES only when safe initialization cannot continue without resolution.

| ID | Category | Statement / decision | Temporary default | Impact if false | Owner/validator | Status | Blocks |
|----|----------|----------------------|-------------------|-----------------|-----------------|--------|--------|
| ASM-001 | PRODUCT | Lab-only scope for initial implementation; no production devices touched | Containerlab with 2x IOSv | Tier and rollback design change if prod added | OWNER | CONFIRMED | NO |
| ASM-002 | TECHNICAL | Lab platform is Containerlab with Cisco IOSv images | Containerlab + IOSv | Inventory and render targets change | ORCHESTRATOR | ASSUMED | NO |
| ASM-003 | PRODUCT | Repository stays private until license is selected | no public release | Publishing blocked until owner selects license | OWNER | OWNER_DECISION_REQUIRED | NO |
| ASM-004 | TECHNICAL | NetBox is the intended-state source of truth | NetBox + YAML export cache | Data model and sync tasks change | ORCHESTRATOR | ASSUMED | NO |
| ASM-005 | RISK | Device secrets live in Vault / Ansible Vault, never in Git | Ansible Vault + CI masked vars | Secret handling and audit tasks change | OWNER | CONFIRMED | NO |
| ASM-006 | TECHNICAL | Phase 1 device scope is NTP, DNS, Syslog only; VLAN/interface phase 2; routing DEFERRED | phase plan per REQ-008 | Task graph and gates change | ORCHESTRATOR | ASSUMED | NO |
