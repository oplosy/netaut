# Pull request checklist

- [ ] `python scripts/ci_gate.py --sample netbox/intended/sample.yml` green
- [ ] `pi_check all` green (when `docs/` orchestration files change)
- [ ] No secrets, vault material, or live addresses in the diff
- [ ] Task-sized work links its `reports/<TASK>.txt` evidence
- [ ] Cross-boundary changes link their ACR
- [ ] HIGH-risk work links its `reports/reviews/` approval
