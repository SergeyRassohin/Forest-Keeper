# Stage 9 — independent async API, facts and split-index review

26 October 2026. Read-only review of the initial working delta overa2d4884, committed during review as **4c6325e56dbdedfe9facd1ddb5a3ae51bc5da7d1**, plus explicitly identified uncommitted review fixes. No final frozen-source/runtime acceptance is claimed. Supervisor/container profile is still being implemented separately.

**Verdict: core architecture boundaries are sound; two initial API/UI findings have source fixes, with additional recovery/corruption tests and final integrated verification pending.** Stage9 remains NOT READY; human semantic labels/targets and production activation are not approved.

## Independent execution

- Current30pure contract tests + unchanged independent cancel fixture + two prior artifact/native-identity negatives: **33 PASS,0.96s**, `fk-stage9-independent-api-pure.log`. This independently verifies the previous canceled-request concurrency bug is now closed by faulting admission while the underlying thread may still run.
- AIExplanation initial7component cases PASS881ms; after focus/revocation fix, **8component cases PASS982ms**, `fk-stage9-independent-ui-freshness.log`. Repeated executions are not extra distinct cases. Models/network/private data were not used. No actual model inference, DB/Redis integration or Docker/service mutation by reviewer.
- Root-owned real SQL-split Qwen test and real API/Redis barrier race evidence are separate from reviewer execution. Inspected current ru/en barrier regression log:7PASS43.04s. Host model runtimes are currently stale against new schema hashes, so no new real inference result is inferred from older smoke evidence.

## Positive source boundaries

`routes.py` requires fresh existing conflict.view/decision.view/recommendation.view, current case scope and cookie/Origin; no internal runtime routes exposed. POST explicitly enqueues, GET only polls. UUID handle binds actor, current session hash, case, request ID and queue namespace; RequestRecord expiry/model hash/context fingerprint is checked. Unknown/foreign handles are opaque404, responses inherit no-store. Production is hard-disabled; explanation grants no Decision/write capability.

`facts.py` builds bounded current comparison and actual authorized precedent summaries through deterministic recommendation evaluation and actual lineage validation. No human reasons, actors, raw records or generated prose enter model input. New Facts validators bind current source/value refs, unique/disjoint evidence, group/support consistency and contradiction/status/reason. Output uses permitted clause codes/IDs; render reconstructs text only from freshly verified current Facts, preserving human authority and explicit demo limitations.

`explanations.py` creates coherent read-only REPEATABLE READ snapshots before inference and completed delivery, validates current session/roles/scope/head/config/model fingerprints, then closes SQL transaction/checkout before model work. Long inference does not hold business gates. Completion is audited with safe hashes/IDs/model/prompt/timing; bounded Redis state has TTL and atomic cancel-before-store. Returned model identity is independently verified by transport; expected metadata is not a health claim. Cancellation is explicitly waiting/result cancellation, not an unsupported claim that CPU has already terminated.

`identity.py` binds exact input/output schema hashes as well as artifact/prompt/instruction/runtime versions. Old running gateways with prior schemas are refused. `http_limits.py` bounds small public AI JSON to4096bytes,5s and16incomplete requests while leaving imports/manual routes independent. New Qwen indexing extracts at most8frozen plans, closes SQL/coordination, calls one bounded embed_many, renews token-safe Redis lease, reacquires DB coordination, checks immutable snapshots/current heads/already-checkpointed IDs, then atomically persists. No DB transaction/advisory lock/checked-out pool slot spans that inference. Prior heavyweight backfill finding is resolved in this source shape; actual race/restart/slow-provider proof must still accompany final acceptance.

Frontend sends no hidden AI request on mount/GET, stores no unsaved review data, uses text rendering/validated UUID buttons and explicitly labelled demo identity. Context-key changes abort/drop late work; theme changes preserve draft and component identity. No AI response triggers a business POST.

## Findings and current disposition

### 1. Completed explanation freshness — fixed in source/test

Initial UI stopped polling whenCOMPLETED and had no focus/visibility recheck; previously authorized evidence could remain visible after server scope/head/model changes. The reviewed correction retains30s completed polling/focus/visibility revalidation, clears completed data before refresh, clears on failure and aborts old poll before a new start. New focus→403 test passes independently and preserves manual draft. Add integrated completed-result scope/session/head/model revocation checks; not only pre-execution stale tests.

### 2. Concurrent same-key payload race — fixed in source; root barrier test passes

Initial POST checked existing language before enqueue but ignored enqueue_boundedFalse after a concurrent winner. Same request_id withru/en could both get202. Corrected route fetches/validates owned winner afterFalse and returns409 on language difference; admission never overwrites an existing RequestRecord, including terminal jobs. Real Barrier(2) API/Redis regression was added and root log7PASS inspected. Final full-suite coverage and duplicate same-payload concurrent tests remain useful.

### 3. Expired handle can trap the UI — follow-up requested

After poll404 the catch clears data/polling but keeps handle; terminal=false then disables new request, while status/cancel may both repeat404. Distinguish definite expiry/missing terminal failure from unknown network outcome: permit a new explicit request after confirmed missing/expired handle, preserve retry for uncertain transport failures, clear evidence in either case. Add404→freshPOST test. This does not break manual review but affects required AI recovery behavior.

### 4. Technical metadata corruption — defensive follow-up requested

record_from catches ValidationError/KeyError but an entire non-dict Job.meta can raiseTypeError; Job.fetch_many is outside owned_job's try. Existing tampered Stored-JSON test does not cover outer job metadata. Validate outer metadata type and return sanitized opaque failure for a corrupted owned handle; never return raw deserialization data. No auth bypass was identified.

## Required remaining verification

Add actual independent integration tests for session/domain/permission revoke during generation and after completion; old/current head/reopen/activation/model/schema/policy/map changes; cancellation before/during/after generation and no late delivery; queue admission expiry/crash/retry; concurrent exact/different request bodies; audit/result storage failure; malformed technical storage; production flags; Qwen duplicate split-batch/lease expiry/crash/mid-inference head change with no SQL resources held. API snapshots and fresh delivery guards are present, but these races are not proved by the initial six stub integration cases.

Runtime cancellation now closes admission, but actual lingering-thread/native termination/watchdog and private container CPU/RAM/PID/network/mount controls remain open. No-egress must include DNS/HTTP and the dedicated worker's second network. Current host loopback smoke is not that isolation proof. New typed facts/schema/prompt require real runtime restart and actual Registry-grounded LLM/browser tests; generated-ID smoke is not a substitute. Real semantic gold/targets remain owner-dependent; no approval is supplied here. Preserve all prior failed runs/provenance, core fallback, strict NFR/real-model load, both-theme visual/accessibility and exact-final-HEAD CI gates.

Reviewer changed no source/Git/runtime/public data, installed nothing and ran no heavy inference. Only temporary reports were written. Re-review the corrected integrated final source and actual evidence before Stage9 acceptance.
