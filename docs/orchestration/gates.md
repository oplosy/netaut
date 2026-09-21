# Readiness gate report (tier HIGH, baseline v1)

| Gate | Result | Evidence | Author | Verified by |
|------|--------|----------|--------|-------------|
| G-01 | MET | docs/registry.yaml | ORCHESTRATOR | script:pi_check trace |
| G-02 | MET | docs/project.md, docs/assumptions.md | ORCHESTRATOR | REVIEW_AGENT |
| G-03 | MET | docs/registry.yaml, docs/orchestration/tasks/T-000.yaml, docs/orchestration/tasks/T-001.yaml, docs/orchestration/tasks/T-002.yaml, docs/orchestration/tasks/T-003.yaml, docs/orchestration/tasks/T-004.yaml, docs/orchestration/tasks/T-005.yaml | ORCHESTRATOR | script:pi_check trace |
| G-04 | MET | docs/registry.yaml | ORCHESTRATOR | script:pi_check trace |
| G-05 | MET | docs/architecture.md, docs/decisions/ADR-003.md | ORCHESTRATOR | REVIEW_AGENT |
| G-06 | N/A | Lab-only automation; no personal or sensitive user data processed or stored | ORCHESTRATOR | REVIEW_AGENT |
| G-07 | MET | docs/architecture.md, docs/decisions/ADR-001.md, docs/decisions/ADR-002.md, docs/decisions/ADR-003.md, docs/decisions/ADR-004.md | ORCHESTRATOR | REVIEW_AGENT |
| G-08 | MET | docs/architecture.md, docs/orchestration/tasks/T-003.yaml | ORCHESTRATOR | REVIEW_AGENT |
| G-09 | MET | docs/orchestration/tasks/T-000.yaml, docs/orchestration/tasks/T-003.yaml | ORCHESTRATOR | script:pi_check trace |
| G-10 | MET | docs/orchestration/state.yaml | ORCHESTRATOR | script:pi_check graph |
| G-11 | MET | docs/orchestration/tasks/T-003.yaml, docs/orchestration/state.yaml | ORCHESTRATOR | REVIEW_AGENT |
| G-12 | MET | docs/orchestration/gate-review.md | ORCHESTRATOR | REVIEW_AGENT |
