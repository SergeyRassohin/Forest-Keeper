# Stage9 — independent planner-boundary and actual-AI browser-harness review

26 October 2026. Read-only source/evidence review of b546984 plus the uncommitted planner restoration, regression, fixture/Compose/Playwright delta. No source/Git/deployment/public-data changes, inference or model restart by reviewer in this follow-up. Earlier independent real-Qwen and no-egress execution remains separately recorded in `stage9-supervisor-v5-independent-review.md`.

## Planner source verdict

The previously observed transaction-local planner-setting leak is real, not a test waiver: root pre-fix regression failed in7.41s, and targeted after-fix planner + exact committed-reference retry regressions passed2cases in12.93s. This evidence was inspected; reviewer did not independently rerun SQL tests in this follow-up.

`backend/app/similarity/service.py` now reads current enable_nestloop/jit, applies ranking hints only for the bounded ranking SQL, eagerly fetches its limited page with .all(), and restores both exact caller values before Python provenance processing, additional receipt/lineage SQL or Decision writes. Main ranking predicates, ordering, threshold, eligibility, scoped counts and result-page cap are unchanged. Caller on/on, on/off, off/on and off/off combinations are covered. At most the bounded result page and singleton diagnostics are materialized by .all(); this does not load the full history into Python.

A ranking SQL failure leaves PostgreSQL transaction aborted; the caller must roll back and no restoration SQL is attempted against an aborted transaction. Decision route ApiError/SQLAlchemyError handlers do roll back; transaction-local settings then disappear before pool reuse. Budget per-SQL monotonic deadlines remain in force for capture, ranking and restore; no deadline/policy relaxation. If restore cannot complete the request must fail rather than proceed to commit. The source shape satisfies that condition.

**No new blocking planner-boundary defect found.** Successful isolated retry does not establish that all initial receipt RECOMMENDATION_TIMEOUT failures are gone: repeat full current regression/exact-head CI and keep original local/CI failures visible. The causal planner leak is demonstrated; load-wide timeout resolution remains a separate measurement.

## Browser harness boundaries and evidence

Fixture creates a unique auth_test disposable schema and unique stage9-ai-browser queue namespace, imports synthetic cases and five actual confirmed Decisions, uses genuine Qwen embedding backfill, saves private0600 fixture credentials without printing them and restricts cleanup by owned schema/queue patterns. New Compose profile is separate from runtime, read-only/non-root/capability-free/bounded, uses private key secret and operator-selected existing DB/model bridges, and does not add an AI host port. External bridge internal flags must refer to the already verified owned profile; selecting an arbitrary external network is not itself an isolation assertion.

Playwright uses explicit owned model project validation and Compose labels before stop/start, no shell command interpolation, existing HttpOnly browser auth and real backend/model queues. It explicitly requests grounded AI, verifies actual model metadata/citation subset, draft/radio state and no browser-originated Decision POST until separate human save. It visits Registry/cited authorized Decision, saves human Decision, then stops both explicitly owned models, confirms AI fallback with manual draft intact and saves another explicit human Decision. Model text never generates a write payload. Trace/video/automatic error screenshots are disabled so login credentials do not enter shareable artifacts. The actual existing root browser report is development-synthetic evidence, not human gold.

Independent report/artifact checks PASS:8PNG SHA256 exact equality,8zero-Axe reports,20responsive checks. Manually inspected dark390 actual explanation and light1440 both-models-stopped screenshot: legible demo limitation/current values and available manual form. Browser execution itself was root-owned, reported PASS2.0min; reviewer did not repeat it or infer model readiness from a running test.

## Concrete harness follow-ups sent to root

1. `tests/ai-browser/actual-ai.spec.ts` finally currently only docker starts models, with no bounded healthy wait, and report.passed=true is set before restoration. Start acknowledgement alone does not prove restored working models. Record/assert bounded current-container readiness, or qualify restoration evidence accurately; original stopped/running state should be explicit for reuse. No repeated inference is necessary to prove health.
2. A docker-start exception currently occurs before writeFileSync(report); it can prevent preservation of the failed report. Use nested finally/report write so restoration failure remains an explicit failed artifact and does not overwrite successful history as PASS.
3. `backend/tests/ai_browser_fixture.py` cleanup uses auth_rate_prefix from its private fixture as a Redis glob. Validate it equals the already validated schema + ':' before scanning, matching strict queue/schema ownership checks. The private0600 fixture is trusted owner input; this is defensive cleanup safety, not a discovered public attack path.

These are acceptance-harness/recovery-evidence findings, not a new business authorization defect. Re-review source corrections before closing them.

## Stage verdict

Checkpoint source review positive subject to the concrete harness follow-ups. Stage9 remains NOT READY: human-approved gold/targets, representative real-vector10k/concurrent AI/core performance, final full regressions/security/browser/recovery and exact-final-HEAD CI remain open. No merge/production activation/next-stage approval is provided.


## Follow-up source acknowledgement

All three concrete harness findings are corrected in the current working tree, independently re-read without inference/restart: cleanup requires auth_rate_prefix exactly equal to the validated owned schema + ':' before any Redis scan; browser restoration waits for both explicit model containers to report healthy with a bounded180s poll and5s per inspect; nested finally always attempts report preservation, and report.passed requires both flow_passed and models_restored_healthy. Start/health failures therefore cannot be labelled a successful accepted run. These source findings are closed. The previous successful browser artifact remains historical, not relabelled as execution of the corrected harness; parent will rerun on a fresh owned fixture/current image. No additional source blocker identified. Final Stage9 acceptance/exactCI/performance/gold boundaries remain pending as above.
