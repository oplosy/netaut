# Adversarial gate review (baseline v1, tier HIGH)

Reviewer: REVIEW_AGENT (fresh context, task specs + cited evidence only).
Date: 2026-09-21.

## Challenges
1. G-03 coverage: REQ-008 DEFERRED has no task. Falsify: is DEFERRED used to
   hide routing scope? Disposition: REJECTED as failure. REQ-008 explicitly
   DEFERRED in docs/registry.yaml; pi_check trace excludes DEFERRED from the
   live-implementation rule. Phase boundary recorded in ASM-006.
2. G-04 INV-002/INV-003 verified by review of docs/architecture.md only.
   Falsify: prose is not execution. Disposition: ACCEPTED with teeth.
   At init time no code exists to test; review refs are the correct mechanism
   per skill, and T-001/T-002/T-004 carry preserves obligations that force
   test-time enforcement during execution.
3. G-11 HIGH task T-003 has no DONE review evidence yet. Falsify: gate claims
   review without a review file. Disposition: ACCEPTED as init-readiness
   (not execution-readiness). Evidence cites the review_required flag plus
   state gating; reports/reviews/T-003.md becomes mandatory before T-003
   may move to DONE. No HIGH task is DONE today.
4. Image/API versions UNVERIFIED (ASM-002, ASM-004). Falsify: architecture
   rests on unknown versions. Disposition: ACCEPTED with condition. Pinning
   is a T-000/T-001 entry criterion; ACR required if versions invalidate
   the render approach.

## Verdict
All MET claims survive or are conditioned above. No N/A/WAIVED abuse.
Initialization may proceed to wave 1 (T-000).
