# Stage 8 — independent final application review

25 October 2026 · [Issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29) · [PR #30](https://github.com/SergeyRassohin/Forest-Keeper/pull/30).

Application candidate: `cd5116c4569389658bb046c197db45221c593ccd`.
Backend application tree: `0a79a1e89317b3bd3ff5da81bf64168ae1fde191`.
Frontend source tree: `cf5309eac8b8f2929c98b975eadf966da3243282`.

**Independent local acceptance: PASS.** Source, targeted security/product tests, full553integration,15HTTPS browser, runtime/performance/visual/security evidence pass on the reviewed application. Exact-final-HEAD push/PR CI remains the release boundary. This review does not grant merge authorization or substitute for the owner's separately recorded policy approval.

Repository evidence: [acceptance](stage8-acceptance-2026-10-25.md), [performance](stage8-performance-2026-10-25.json), [runtime/restart](stage8-runtime-2026-10-25.json), [production smoke](stage8-production-2026-10-25.json), [acceptance scenario](../stage8-acceptance.md). Local log basenames below are execution provenance; summaries and structured artifacts above are the reviewable repository records.

## Independent execution

Reviewer executed at exactcd5116c:

```text
pytest -q backend/tests/test_recommendations_integration.py -k 'isolated_integrity or integrity_boolean or skipped_outcome or (corrupt_persisted and payload_array) or exact_committed or total_monotonic or two_real_reviewers or scope_revoked_after or reopen_waits or retrieval_activation or five_real_independent or begin_review_refresh or production_refuses'
```

**15 PASS,29deselected,62.04s**, log `fk-stage8-independent-final-candidate-tests.log`. Each test creates/cleans its own disposable auth_test schema and unique queue/storage/rate namespaces. No source/Git/runtime/public-data mutation by reviewer; credentials were not printed. Test durations are not performance claims.

Tests verify real five-independent-file histories/current-value proposal/no business GET writes; begin-review refresh/human acceptance/idempotency; production synthetic fail-closed and manual independence; exact committed retry without Redis/re-evaluation; stored whole-audit-array corruption refusal; per-SQL remaining deadline/gate release; isolated integrity SQL failure with **same DBAPI connection** reset, integrity-off/ranking-on phase observation, recovery and manual save; compatible MASS versus incompatible PRICE corruption/skip; two-reviewer201/409; reopen barrier; fresh scope revocation after preflight; retrieval-version stale reference with independent manual save.

## Architecture, product intent and policy

Separate deterministic module uses existing authorized structured history and authenticated read-only REPEATABLE READ snapshot. No new provider, Qwen/LLM, external AI call, training, write-back, RuleSuggestion, shadow rules, automatic Decision or canonical state is added. Stateless RecommendationResult plus bounded immutable audit receipts avoids a new Recommendation SQL table/migration. Human Review remains the only business commit path with existing XLSX permissions, cookie+Origin, domain scope, current token/head/value checks, explicit confirmation and persistent idempotency. ADMIN alone gains no business authority.

Owner-approved policy remains minimum5 independent provenance components, unanimous support/contradiction veto, maximum20 complete above-threshold pool and existing full-precision similarity threshold. Current-sentinel transitive grouping and shared file/raw/key/semantic edges prevent clone support. Source correspondence uses versioned server declarations and actual lineage; historical IDs cannot become current values. Confidence is group count, not probability/cosine. Production is UNAVAILABLE; absent/stale/ambiguous authority or lineage never invents truth. All14carry-over dispositions retain owners/acceptance limits. #17/#18/#20, production semantics,100k, fully cold caches and license/update/offline supply remain separate.

Referenced-save gate checks admission auth before exclusive acquisition, refreshes auth/ORM after waiting and uses gate-before-row-lock order under the remaining deadline. Manual saves retain provider/Redis independence. Configuration replacement explicitly requires quiesce/drain; unsupported mixed-version hot activation is not claimed.

## Resolved findings

- Phase-only deadline: per-SQL remaining timeout hook, outer-transaction teardown and pre-commit refresh.
- Syntactic provenance: bounded actual raw/import/value/normalization/matching projections, historical Conflict hash and selected-value checks.
- Refresh route loss: validated UUID-only URL recovery; theme persists presentation without storing reasons/secrets or modifying evidence.
- Audit integrity/error handling: basis/event/object/actor/case/stable-ID/time/outer-payload checks and sanitized corruption refusal.
- Redis before exact retry: authorized committed-key lookup precedes new search/provider budget.
- Five good plus skipped contrary history: Stage8 strict scoped compatible-vector completeness, independently proven red→green; Stage7 skip contract preserved.
- Fresh-page planner hash scan: isolated exact predicate/version/scope integrity query prefers existing partial index only during that query and restores prior settings before ranking/after fault. No integrity/NFR weakening.
- Diagnostic artifact permissions:0600/O_NOFOLLOW before writing secrets.
- Scene29 filled-form screenshot missing: corrected actual form target and all4replacement variants independently viewed.

**No outstanding application-source, architecture/security/product or critical visual blocker found.**

## Current acceptance evidence reviewed

- `check-final`:278unit/64component PASS; lint/mypy70/typechecks/production build PASS. Final SAST zero issues, secrets no leaks, dependency audits zero known vulnerabilities; unsafe B602/eval/PAT fixtures rejected.
- Detached exactcd5116c regression worktree independently checked against both source trees: **553integration PASS303.20s +15real HTTPS browser PASS1.1m**, verified in final full integration log.
- Real HTTPS gallery exactcd source: **124PNG/124accessibility/310responsive PASS**. Reviewer opened scenes20/28/29/30 light/dark desktop/mobile, including corrected scene29 selected radio, entered human reason and separate review-before-save button. Warnings/confidence/current correspondence/contradiction abstention/modal readable; no critical clipping/overflow. Screenshots do not alone prove independently measured numerical contrast or keyboard execution.
- Fresh exactcd actual HTTPS runtime/restart report PASS: five real separate file pairs, stable receipt/full Decision aggregate across full restarts, durable partial checkpoint recovery, explicit activation/stale receipt, PostgreSQL503/recovery, Redis-down manual save/exact retry, default fail-closed and Registry independence. Actual production four hardening/upload/worker/persistence groups PASS. Captured backend imagee1026957 and frontendfdc75381 are preserved in reports.
- Final frontend image6750877b only embeds refreshed static gallery archive; root verifies served manifest equals tracked and JS/CSS hashes match unchanged captured bundles. Application frontend tree remainscf5309ea. Current uncommitted delta is docs/reports/static gallery, with no application source change.
- Exactcd performance report: **350requests,10sessions,zero failures,passed=true**; positive5case p95=.858970s;100/1k/10k Stage8p95=.693262/.528532/.910828s,10kbaseline=.618654s,Stage8max=.956232s. Two same-code forced fresh/bloated10k relallvisible0 rounds retain Stage7p95=.758667/.953367s and Stage8=.780239/.756529s; one Stage7max1.160576s is visible and does not violate the p95 criterion. Earlier failed runs remain failed; causal visibility diagnosis and repeated fresh-page measurements support the fix instead of cherry-picking a lucky sample.

Performance is warm in-process ASGI with actual PostgreSQL/Redis and synthetic replicated Decision/vector rows, large-pool EVIDENCE_WINDOW_EXCEEDED plus separate genuine5case positive. It is not100k,10k independent positive recommendations, industrial semantic quality, fully cold OS, total container RSS or independent external MVP acceptance. HTTPS transport is verified separately.

## Delivery boundary

Preserve this report/evidence, commit only reviewed artifacts/docs, and verify the new exact final SHA retains both application trees. **Green exact-final-HEAD push and PR CI and final independent SHA acknowledgment are still required before READY TO MERGE.** Do not merge automatically or close #17/#18/#20. Owner alone decides merge.
