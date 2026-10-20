# Stage 4 entry architecture gate — independent read-only review

Date: 2026-10-20. Reviewed main 992e52641cef89a19dcb5c9db3045617e9b15111 and Stage4 issue14 specification supplied in /tmp/fk-stage4-spec.md. No application/docs/GitHub/container changes; no capacity/browser execution.

## Result

Stage3 runtime is compatible with the new product/Gold Reference invariants. Entry is conditional on correcting current-state documentation and recording this architecture gate before starting Stage4. No mandatory Gold Reference UI/history/activation implementation belongs in this boundary patch.

Reviewed AGENTS mandatory stage gate, stage-gate-checklist-v0.1, current Decision Log, product roadmap, canonical data model, AnalysisRun/MatchCandidate lifecycles, actual XLSX matching/analysis permissions, normalization models/migration/history design, normalization/API docs and Stage3 acceptance/progress docs.

## Concrete drift and minimal corrections

1. docs/development/mvp-progress.md:41 says canonical is unimplemented; line57 says Stage3 has not merged. Stage3 normalization/CanonicalEntity/EntityValue exist on reviewed main. Qualify old iteration text as historical; update current status with actual Stage3 merge SHA and successful merge CI evidence. Do not invent CI evidence or replace measured runtime SHAs.
2. docs/testing/reports/stage3-normalization-acceptance-2026-10-20.md:3 still says merge not performed. Append factual acceptance/merge confirmation and add the now-mandatory `Architecture / Product Intent Gate` section with explicit intent/raw/provenance/human/AI/Gold-versioning/impact answers. Retain historical pre-merge results and their SHA context.
3. Record Stage4 architecture choice before implementation: completed normalization runs and their immutable origin/output facts must not be reopened or repurposed as mutable matching executions. A minimal technical run association/infrastructure using the existing canonical AnalysisRun lifecycle is permissible only with an explicit documented decision and disjoint run type/inputs, or use documented technical matching-run infrastructure. Preserve existing /analysis normalization contract and old history.

## Why Stage3 is compatible

Raw, provenance, original attribute values and mapping snapshot/hash/engine are retained. UUID representation identity includes raw UUID and mapping fingerprint; new fingerprints preserve old facts instead of rewriting them. There is no Gold Reference/customer activation, rule-learning or automatic baseline mutation. The current config profile is explicitly not CustomerTemplate or Gold Reference. CanonicalEntity status NULL is an explicit accepted decision, not an invented truth/merge state. Existing inputs and their snapshot lineage support future dependency lookup; absence of Gold activation means a complete active-reference/impact UI is not a present runtime defect.

## Constraints for Stage4

- Implement canonical MatchCandidate fields id/raw_record_a_id/raw_record_b_id/confidence/evidence/status/confirmed_by/created_at. Start POSSIBLE_MATCH and use only transitions to MATCHED/NOT_MATCHED; preserve terminal history. Automated exact disposition needs explicit versioned rule evidence; confirmed_by records a real human only. Do not overload match status with STALE or create new canonical enums silently.
- Pair uniqueness is unordered and self-pairs forbidden. Scope pair facts to immutable input/profile/engine/threshold context and run association, not a global raw pair constraint that prevents future profile reevaluation or silently overwrites old evidence.
- Bind every matching execution/result to exact completed normalization run IDs, raw IDs and EntityValue/representation IDs or equivalently reconstructible snapshot lineage; persist matching profile snapshot/hash/version, scoring engine, signal contributions, blockers and threshold decision (including explicit absence of fuzzy-auto threshold). Never read latest mapping and reinterpret history.
- Exact MATCHED only for explicitly declared trustworthy identity semantics in synthetic versioned profiles, with hard-negative/conflicting strong-key blockers. Name/price/mass similarity alone is not identity. Rule/fuzzy scores may explain confidence but remain POSSIBLE_MATCH without an accepted production threshold. Deterministic negative rules can reject only with preserved evidence. Candidate omission is not automatically a persisted NOT_MATCHED judgment.
- Bounded blocking/candidate caps must expose truncation/coverage; never label incomplete generation complete without diagnostics. No 100k squared comparison. Synthetic benchmark ground truth is not customer Gold Reference and grants no auto-activation authority.
- XLSX actually contains analysis.run (REVIEWER/DATA_OWNER/ADMIN), analysis.view and match.view (all four business roles), match.review (REVIEWER/DATA_OWNER only). Use match.view for candidate/evidence reads, analysis.run for execution, match.review for manual disposition; ADMIN alone must be rejected. Mandatory cookie/Origin/backend authorization and audit remain applicable.
- Preserve Stage3 append-only CanonicalEntity/EntityValue/AnalysisRecord and origin snapshots. Do not physically merge/delete entities, change truth values, or write back. Stage5 Conflict/Recommendation/Decision logic is outside scope.
- Future Gold Reference linkage must be nullable/explicitly NOT_APPLICABLE until real CustomerTemplate/Gold versions exist, not a fake immutable customer baseline. Keep dependency IDs/hashes sufficient to find affected evaluations later. Profile changes already require new run/results; surface historical profile context separately from currentness.
- Gold activation/rollback later requires author/approver/reason/parent/scope/diff/snapshot/audit, preactivation impact+warning, then explicit re-evaluation/stale marking. Do not mutate historical matching evidence to mark currentness: use separate technical applicability/dependency metadata or derived comparison, while preserving canonical MatchCandidate lifecycle.
- CustomerTemplate lifecycle DRAFT→ACTIVE→SUPERSEDED forbids silently reactivating SUPERSEDED history. Safe rollback creates a fresh version based on the older content, explicitly approved and audited. Raw/normalization snapshot reuse is not Gold rollback. Full Gold workflow/UI belongs to agreed later Rules/CustomerTemplate stages (11–12), not Stage4.

## Limits

This is a fresh architecture/document entry review, not a new technical acceptance run or CI attestation. Prior Stage3 independent tests are historical evidence; no Stage4 implementation exists to validate yet. Actual merge CI reference must be verified by the implementing parent. Final Stage4 needs the separate issue14 §32 independent runtime/security/browser/migration/benchmark retest.

## Implementer resolution / entry acceptance

Documentation drift corrected before Stage4 application implementation. Stage3 merge6a49453 mainCI39452965438 SUCCESS; current documentation-only main992e526 mainCI39463391754 SUCCESS. Application tree did not change between these main commits. Historical measurement/review SHAs are retained. The stage entry architecture gate is PASS; full Gold workflow is deliberately deferred to roadmap stages11–12. The Stage4 technical run decision below is recorded before implementation.
