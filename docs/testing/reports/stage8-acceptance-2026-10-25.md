# Stage 8 — acceptance evidence, 25 October 2026

Issue [#29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29),
PR [#30](https://github.com/SergeyRassohin/Forest-Keeper/pull/30),
branch `codex/stage8-recommendations`. **Acceptance in progress; not READY TO MERGE.**
Base accepted main: `c927af513d29d83bd53b1b6522efccb42b5a1341` / Stage7 PR #28.
Owner approved eight policy points in chat on25October; this is implementation
authorization, not merge authorization. Historical proposal pending status is preserved.

## Scope and architectural conformance

Separate deterministic service uses authorized structured history and current values.
RecommendationResult is stateless with bounded append-only audit receipts; no migration,
new canonical state, SQL Recommendation table or permission is introduced. Existing
human-confirmed Decision POST is the only business commit path. Existing XLSX39 permissions,
cookie+Origin, domain scope, tokens, immutable history and persistent idempotency remain.
The receipt bridge revalidates fresh auth/evidence under a bounded cooperating-write gate.

Policy `stage8-demo-unanimous-v1`: five independent groups,100%agreement,0contradiction,
weight1, margin1; complete above-threshold pool<=20, existing inclusive similarity>=.85.
Confidence is independent-group count, never synthetic score/probability. Shared file/raw/
business-key/semantic connected components, including current sentinel, prevent cloned support.
Explicit versioned actual-source correspondence; no source-name/order authority inference.
Current IDs are selected; historical ENTER_VALUE is not copied. Production always fail-closed.

Rules/Template/Codex are NOT_CONFIGURED, authority NOT_DEFINED. No AI/LLM, new provider,
external egress, training, RuleSuggestion, automatic resolution, source modification or write-back.
Theme/validated URL recovery are presentation-only and do not enter Decision evidence.
Stage6 Human Review+Registry → Stage7 Retrieval → Stage8 Recommendation → next Stage9 AI.
Historical roadmap numbering is not rewritten.

## Verified checkpoints and remaining gates

- Source checkpoint `4d051c8`:547 integration PASS248.58s;15 real HTTPS browser PASS58.6s.
  Backend278 unit and frontend64 component PASS at the implementation checkpoint.
- Independent review found compatible legacy skip could hide an opposing outcome. On4d051c8
  its owned-schema regression was RED:5 indexed supporters+1 skipped opposite gave RECOMMENDED.
  `49b4c1a` adds a private scope-first complete-vector gate; same independent test PASS5.30s.
  Stage7 public skip/retrieval semantics are preserved. Incompatible skipped PRICE case
  does not block MASS recommendation; whole-audit-array corruption safely refuses.
- Independent targeted review:15 distinct cases pass across those checkpoints;
  the original12-case selection PASS46.28s and3-case fix/incompatible/corruption selection
  PASS18.35s. Final source/evidence acknowledgment remains pending.
- Updated targeted local5-case coverage/receipt/positive tests PASS20.36s on49b4c1a;
  incompatible skip retained in repository as an additional regression.
- Ruff/mypy70 source files, Bandit and frontend security ESLint PASS. Dependency scans
  report no known vulnerabilities; Git-history/tracked-tree gitleaks PASS. Deliberately unsafe
  B602/eval/PAT fixtures are rejected. Final-HEAD rerun/CI remains mandatory.
- Both-theme gallery, full suite after review fixes, performance100/1k/10k, actual restart/
  recovery, production hardening smoke and exact-final-HEAD GitHub push/PR CI: **pending**.

No earlier checkpoint or sum of repeated runs is presented as final acceptance.
Reproducible commands and manual expectations: [test scenario](../stage8-acceptance.md).
Final source/evidence and CI links will be recorded before READY TO MERGE.

## Stage7 carry-over register — all14 dispositions

Owners below identify the responsible workstream; they do not imply implementation
of deferred systems. Owner approved these boundaries with the Stage8 policy proposal.

| # | Disposition | Owner and acceptance criterion | Stage8 evidence / retained blocker |
| --- | --- | --- | --- |
| 1 production embeddings | BLOCK_PRODUCTION_RECOMMENDATION | Stage9 implementer + product owner: accepted real provider, versioned artifacts, industrial semantic validation/offline installation | Production flags fail-closed regression; synthetic demo clearly labelled. No positive production claim |
| 2 capacity100k | DEFER_WITH_OWNER_AND_ACCEPTANCE | Performance owner + product owner: separately measured100k actual rows, realistic distributions,10sessions | Stage8 harness measures100/1k/10k only;100k remains unverified |
| 3 diversity/independence | RESOLVE_STAGE8 | Stage8 implementer/reviewer: real separate imports vs clones/transitive current correlation | Unit graph boundaries; real5 independent / repeated imports /5:1 integration and browser fixtures; capacity clones are explicitly synthetic |
| 4 cold proof | DEFER_WITH_OWNER_AND_ACCEPTANCE | Performance owner: controlled OS+DB cold profile before fully-cold claims | Report warm profile and retained OS cache; restart proves persistence, not fully-cold performance |
| 5 unit/family compatibility | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product/domain owner: approved dimension/family mapping and regression fixtures | Exact canonical domain/entity/attribute/type/unit retained; no inference or expansion |
| 6 legacy source roles | RESOLVE_STAGE8 | Operator + Stage8 reviewer: explicit scoped versioned actual source identities/types/profile hashes | Missing/ambiguous/wrong type/new mapping tests; unknown correspondence abstains |
| 7 Rule/Template/authority/Codex | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product/domain owner + future #17 implementer: active scoped versioned configuration and precedence acceptance | NOT_CONFIGURED/NOT_DEFINED; apparent unsupported authority abstains; no shadow rules |
| 8 confidence/calibration | RESOLVE_STAGE8 | Product owner/reviewer: approved deterministic evidence measure, adversarial cases | Versioned group-count policy,0/1/4/5/20/21 boundaries; no probability or cosine confidence |
| 9 races/revocation/cache | RESOLVE_STAGE8 | Stage8 implementer/security reviewer: coherent snapshot + atomic referenced save | Real201/409 two-reviewer, reopen barrier, scope-revoke barrier, version stale, persistent retries; runtime report required |
| 10 integrity/coverage | RESOLVE_STAGE8 | Stage8 implementer/security reviewer: no partial positive on corrupt/unknown compatible evidence | Actual lineage projections, corrupt receipt/vector regressions; compatible skip blocks, incompatible skip does not |
| 11 timeout/load | RESOLVE_STAGE8 | Stage8 implementer/performance reviewer: shared120/min, total protective1500ms, NFR p95<=1s at10sessions | Per-SQL remaining deadline/gate release/pool reset and shared-rate tests; performance report required |
| 12 documentation drift | RESOLVE_STAGE8 | Stage8 implementer/reviewer: actual main/PR status, explicit new numbering and runtime contract | README/progress/architecture/API/model/lifecycles/current contract updated; historical records preserved |
| 13 external vertical | DEFER_WITH_OWNER_AND_ACCEPTANCE | External reviewer + product owner, #18/#20: independent own-file fresh install through full accepted MVP | Stage8 own-file HTTPS demo supports deterministic segment; Qwen/provider/external MVP acceptance remain open |
| 14 license/update/offline supply | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product + deployment/security workstream: separate signed/versioned supply and installer acceptance | Existing trust boundaries preserved; no new license/update claims or scope expansion |

## Remaining approval boundary

Do not merge automatically or close #17/#18/#20. Final CI must match the final branch
HEAD for both push and PR. Once local acceptance, independent final review and CI pass,
mark READY TO MERGE and leave the merge decision to the owner.
