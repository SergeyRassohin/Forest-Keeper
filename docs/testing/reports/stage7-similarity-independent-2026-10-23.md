# Stage 7 independent architecture/security/product-intent review

Reviewer: independent read-only review agent. Date: 2026-10-23 (UTC; user-facing project date Europe/Moscow).

Scope: issue #27 / AGENTS mandatory stage gate, branch `codex/stage7-similar-decisions`, accepted Stage6 main merge `0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852` (reported exact merge CI39947944543 SUCCESS). This is an initial design review only, not final acceptance. No application code, git history, service, database, fixture or deployed configuration was changed by this reviewer; only this `/tmp` record was written.

## Provider boundary conclusion

**The proposed bounded Stage7 provider configuration is permitted by the explicit issue, subject to honest scope and tests. No additional user approval is inherently required solely because the production provider is unavailable.** Issue27 §8 expressly allows a deterministic provider for tests and a production adapter interface when no real provider has been accepted. §4 expressly permits honest retrieval-unavailable while Decision Registry/history continue functioning. These later issue requirements govern this iteration over the broader future Qwen architecture baseline.

This is not acceptance of production semantic retrieval. The release must state that no real production embedding adapter/model runtime is configured and that semantic quality is not proven by test embeddings. Production must fail closed to a distinct unavailable response. Development/test success, actual pgvector use and genuine Decision IDs are still mandatory; tests cannot be replaced with canned/mock retrieval results.

Required provider controls:

- Default production provider unavailable; no hidden model download, external API, OpenAI/ChatGPT, LLM/Qwen runtime or enterprise-data egress.
- Test provider selected only through explicit trusted development/test configuration and a second explicit opt-in; production mode must reject the test provider at startup/config validation, rather than merely display a warning.
- Test vectors have a separate test provider/model ID, fixed exact algorithm revision and explicit test-only metadata. They must never be labelled as Qwen output. Keep the 1024-dimensional baseline for this iteration; preserve pinned future Qwen contract metadata separately from actual generated-vector metadata.
- Versioned input/preprocessing/model/revision/dimensions and input/content hashes must remain reproducible. Do not use process-randomized Python hash or whole repository HEAD as a provider revision that changes on unrelated documentation commits.
- Reject wrong dimension, NaN/Infinity, zero-norm cosine inputs, oversized input/output and invalid numeric payloads. Failures cannot break core Conflict/Human Review/Decision endpoints.

## Minimal precedent policies recommended before implementation

1. Use only SELECT_VALUE / ENTER_VALUE Decisions that are currently the effective head and whose source Conflict is RESOLVED. Source context must be complete and integrity-valid. Exclude DEFERRED, INSUFFICIENT_DATA, SUPERSEDED, query's own Conflict, and unresolved/IN_REVIEW source cases. In Stage6, explicit correction keeps the old head ACTIVE while the Conflict becomes IN_REVIEW; checking ACTIVE/no-successor alone therefore does not satisfy issue27's unresolved exclusion.
2. Recheck current eligibility and persisted user scope in the SQL retrieval query even if an old embedding exists. A stale vector cannot grant access or keep a superseded/reconsidered Decision in active retrieval.
3. Detect synthetic cases from frozen declared profile/dataset metadata or another explicit trusted dataset policy; do not rely on actor login/name heuristics. Existing Decision has no is_test business flag. Production excludes synthetic cases; explicit test-mode fixtures may permit them without mutating Decision.
4. Build retrieval input from immutable historical context, keeping normalized value semantics, source types/roles, known unknowns, frozen profile/engine/template/authority metadata. Exclude transient UUIDs, timestamps and secrets/raw payload from similarity features, but retain immutable IDs for provenance/integrity validation outside the embedding text.
5. Use exact domain/entity/attribute/conflict type and compatible canonical kind/unit filters until an approved family/dimension map exists. Unknown or ambiguous compatibility fails closed. Query context and precedent should use the same versioned builder.
6. Define score metric/range/distance transform, inclusive threshold semantics, precision/tie ordering, default/max limit and pagination explicitly. Do not expose arbitrary client threshold overrides without an approved permission/config policy.

## Privacy, counts and no-precedent states

All candidate counts, including total_candidates_before_filter, must describe the authorized scoped pool rather than inaccessible global history. Apply scope/current-head/status/compatibility predicates inside the SQL search before ORDER/LIMIT; do not fetch a global top-K then remove unauthorized rows in application code.

Avoid foreign-data existence oracles through empty-state messages. A restricted user with no scoped history can receive NO_ACCESSIBLE_PRECEDENT without learning whether other domains have history. A wildcard reader may distinguish globally empty permitted history. Compatible-zero, all-below-threshold, scoped-index-building and provider-unavailable need distinct honest states; public responses must not reveal global private backfill counts.

Permissions should reuse the actual XLSX/catalog, not role-name inference. Read requires existing Conflict/Decision access. Backfill/reindex/model activation is a trusted audited control-plane operation; use an explicitly justified existing technical permission or a bounded administrative CLI, rather than silently allowing any REVIEWER to activate models.

## Indexing/recovery and performance review reminders

- Persist unique Decision + embedding-version representation and immutable model/input metadata. Derived index facts can coexist across versions; ordinary Decision/audit facts remain append-only.
- Backfill must be bounded, idempotent, restartable and audited, with reasons for skips. Version activation and active-version coverage must be explicit. Timestamp checkpoints alone can miss late-committing Decisions; detect missing live eligible rows and never silently label a partial version ready.
- FK-NFR-PER-004 places embedding/backfill work in background jobs rather than a long blocking HTTP request. Keep query/provider work bounded and Registry independent.
- FK-NFR-CAP-002 requires a similarity profile with at least 10,000 persisted Decisions. Issue27 permits reporting a 100k-Decision limitation; it does not turn a 100k-Conflict queue into a 10k-Decision benchmark.
- Publish test-provider capacity separately from production semantic quality; include real pgvector plans, cold/warm/concurrent timings, throughput, RSS and database/vector-index growth.

## Independent final acceptance remains pending

Read finished model/migration/provider/context/service/routes/backfill/UI and docs; independently execute compatible/unrelated/scope/supersede/reconsideration/backfill/reindex/failure tests; real browser precedent-ID/detail path and no-provider core-flow survival; restart/partial-index proof; migration/history preservation; security/dependency/full regressions; actual capacity claims; source tree and exact-final-HEAD CI reconciliation. Any blocking findings must be fixed and retested. No merge or Stage8 authorization is implied.

## Initial implementation source review (2026-10-23, uncommitted working tree)

Reviewed `backend/app/similarity/{context,provider,service,jobs,models,routes,cli}.py`, migration 0008, Stage 6 historical context addition, worker/config wiring, new UI and initial tests. Read-only; no services, fixtures, source or Git changed. These findings are preliminary and require re-review of final implementation and evidence.

### Findings sent to implementer

1. **Blocking — incoherent coverage/ranking snapshots** (`service.py:175–228` in initial version). Default READ COMMITTED evaluates counts, missing-checkpoint coverage and ranked pool in separate statement snapshots. A new compatible Decision committed after coverage but before rank is silently excluded by the embedding join and can produce READY with a partial live pool. Use one coherent eligibility/count/coverage/rank snapshot; test a concurrent commit between coverage and rank. Parent acknowledged and is implementing a read-only REPEATABLE READ transaction plus fresh authentication inside it.
2. **Product acceptance gap — concrete explainability omitted from UI** (`frontend/src/SimilarDecisions.tsx:5–9,47–57`). API supplies domain/entity/attribute, evidence summary and explanation, but cards discard these and show only matched feature labels. Issue §13 requires concrete context and why similar, not only names of fields. Show a compact readable historical summary and matching/mismatching values or equivalent explanation. Mandatory disclaimer and honest test-provider warning are present.
3. **Integrity gate concern — false-negative corruption is not validated** (`service.py:221,233–245`). Integrity is checked only for rows already passing compatibility/ranking/threshold. A corrupted vector which drops below threshold, or corrupted artifact compatibility metadata which filters out the row, may become apparent BELOW_THRESHOLD instead of an integrity failure. Include this case in §20 corruption testing and resolve the coverage/integrity design as needed.
4. **NFR acceptance interpretation required** (`service.py:168,241`). Query embeddings and returned historical re-embeddings are computed synchronously. FK-NFR-PER-004 explicitly puts embeddings in background jobs/status flows. Current deterministic test path is bounded and cheap, but document a justified test-only interpretation or move preparation to a background/cache flow; never enable real production embedding work in this synchronous path later.
5. **Remaining security gate**: limit/offset and structured input are bounded, but initial route has no retrieval SQL deadline/concurrency throttle. Issue §§20/27 require timeout and repeated retrieval DoS tests. Parent notified to prove bounded degradation and add budgets as needed.

### Positive source findings

- Real pgvector vectors and scoped exact cosine query; no external network/model runtime/AI recommendation/write-back.
- Default production provider unavailable; test provider requires explicit development/test deployment and explicit opt-in and frozen synthetic profile.
- Scoped current effective RESOLVED SELECT_VALUE/ENTER_VALUE only; no successor, no DEFERRED/INSUFFICIENT_DATA/reopened heads. Excludes query's own Conflict.
- Scope and deterministic compatibility are SQL predicates before rank/limit; restricted empty pool has non-oracular reason code. No inference of scope from role names.
- Bounded top-N/offset, server-owned versioned threshold, deterministic ties.
- Immutable Decision and Conflict source records are unchanged; embeddings/config/items guarded against mutation; unique Decision/version pair; explicit activation and retained old versions.
- Backfill scans anti-join checkpoints, not timestamp watermark, and stores exclusion reasons. Failed batches roll back; previous committed checkpoints survive; per-version execution advisory lock.
- Existing permission matrix is reused; no invented similarity permission or implicit ADMIN business authority.
- New source metadata is frozen for new historical context; legacy missing source metadata remains UNKNOWN instead of being reconstructed.

No final approval yet: final source, runtime/restart/concurrency/security/migration/browser/capacity evidence, fresh independent verification and exact final HEAD remain pending.

## Fix review at fe5de0b290282dd4c7396116bcd6750d364bd2d7

Read-only source/test/documentation inspection; root owns runtime/capacity and requested no test execution while the 4-CPU capacity run is active. Worktree additionally contains root's untracked `backend/tests/restart_similarity.py` harness.

### Initial findings resolved in source

- **Coverage snapshot**: `snapshot_actor` establishes READ ONLY REPEATABLE READ before the first authentication SELECT. Scope/permissions, counts, coverage, artifact validation and ranking share that snapshot. Added SQL execution barrier test commits a new human Decision before ranking and verifies the current request uses the old coherent pool while the next request returns INDEXING.
- **Background embedding NFR**: HTTP no longer calls `embed`. Immutable context/version QueryEmbedding cache is prepared through a bounded RQ job. Missing query representation returns INDEXING/QUERY_CONTEXT_PENDING. Historical HTTP re-embedding removed.
- **False-negative vector corruption**: binary SHA-256 fingerprint matching PostgreSQL `vector_send` plus migration CHECK; a scoped compatible all-pool fingerprint/compatibility scan runs before thresholding. Added hard-storage-corruption test moves a vector below threshold and expects INDEX_INTEGRITY_FAILURE.
- **Concrete UI context**: cards now show actual domain/entity type/attribute/unit and expandable frozen observations, source types, presence/quality/roles and known unknowns, with an explicit compatibility explanation.
- **Query bounds**: 750ms transaction-local statement timeout, per-user 120/min Redis budget, bounded pages/input. Repeated-request 429 test added.
- Backfill recovery uses enum/string value equality, per-version/schema advisory execution lock and anti-join checkpoints. No new business lifecycle or scope inference.

### Additional findings sent to implementer

1. **Query preparation failure appears as perpetual indexing** (`jobs.py:88–90`, `service.py:178–188`). The background task swallows all exceptions and returns success without creating cache data. RQ then records a finished job. GET re-enqueues and continues to return QUERY_CONTEXT_PENDING, so a persistent provider/DB failure is never distinguishable from index building. Preserve a sanitized durable/RQ failure outcome and surface UNAVAILABLE for known failed preparation with explicit retry/recovery. Add a query-path provider-failure test (backfill failure alone does not exercise this).
2. **Browser return-path proof missing** (`App.tsx:228`, gallery test around lines240–244). Opening a historical Decision unmounts Conflicts and preserves matching-run ID but no selected Conflict. The gallery opens precedent and immediately creates an unrelated case; issue §25 steps10–11 require returning to the current Conflict and seeing score/features. Add real return acceptance and restore selection if required.
3. **Withdrawn concern**: snapshot dependency SQL errors before route try are already caught/sanitized by global `main.py` SQLAlchemyError handler. They do not inherently yield500. Explicit route-specific wrapping is optional consistency, and the root's real PostgreSQL-stop harness will verify behavior.

### Capacity/test evidence interpretation

The benchmark persists real immutable Decision/vector rows under DB guards, using disclosed synthetic expansion from one confirmed fixture; it does not simulate 10k independent humans/entities or prove semantic quality. This is suitable to count actual Decision Registry/vector capacity when reported honestly. First query includes direct background-test-helper preparation and is labeled accordingly; it is not cold OS/PostgreSQL cache and not a real RQ end-to-end latency claim. Warm/concurrent measurements use full HTTP handler via TestClient; separate real HTTPS/RQ runtime and browser evidence remain necessary. No final acceptance yet.

## Source review at 00c770e9a52f8ed9be768bc47ed93e50be08d18c

Reviewed changes since fe5de0b, including routes, query failure handling, service integrity predicate, migration partial index, preserved browser navigation and new tests. Worktree was clean at inspection. No runtime/heavy tests executed while parent runs capacity.

**Source verdict: no unresolved blocking architecture, security or product-intent findings.** Final acceptance is conditional on actual gate evidence and exact final HEAD review.

- RQ query preparation now raises sanitized `QUERY_PREPARATION_FAILED` without original exception chaining. Known FAILED jobs return UNAVAILABLE, preserve a 30-second cooldown, and then permit a bounded retry. A dedicated real-RQ failure/retry test checks that sensitive provider text is absent from response and stored exception info. Query job identity includes queue namespace.
- Historical Decision navigation saves the current Conflict and matching IDs; the explicit return button remounts that Conflict. Gallery acceptance now asserts current Conflict visibility, the same precedent ID, score and matched features after return.
- `ix_embedding_integrity` is an acceptable performance fix for application/SQL row integrity: its immutable fingerprint/mismatched hash/dimension predicate is maintained by PostgreSQL on every insert/update. The retrieval query uses the matching literal predicate before thresholding and scopes candidate IDs, alongside compatibility validation. Vector fingerprint CHECK and append-only triggers remain; deliberate SQL-corruption test disables/restores guards only in an owned disposable schema. The index does not claim to detect or repair arbitrary physical page/bit corruption; documentation assigns this to PostgreSQL physical integrity monitoring. This boundary is appropriate.
- The request still establishes read-only REPEATABLE READ before authentication, preserving a coherent scope/permission/eligibility/count/coverage/rank snapshot. Snapshot setup failures now have an explicit sanitized503 fallback in addition to the existing global database handler.
- No new Recommendation Engine, AI/LLM runtime, automatic Decision, hidden network model call or write-back was found.

Remaining acceptance work is evidence, not an identified source defect: final all-gate results, actual HTTPS/RQ/restart/provider/DB failure recovery, browser/a11y/responsive results, >=10k persisted Decision/vector capacity with disclosed synthetic provenance, independent verification against exact final commit, and green exact-final-HEAD CI. No merge authorization inferred.

## Narrow-score CTE performance follow-up (working tree after 00c770e)

Parent reports the required 10k/10-reader run still exceeds the 750ms statement budget, now in ranking. Inspected the uncommitted MATERIALIZED `scored_precedents` / `precedent_page` SQLAlchemy query read-only, without runtime tests while parent prepares an owned persistent EXPLAIN fixture.

No security/product correctness regression found: scope/live eligibility and artifact compatibility remain before distance ranking, one materialized score set supplies both total and page, ties are stable, an empty offset page still retains the correct count, and full historical JSON is returned only for the requested top-N page. The transaction remains a coherent authenticated read-only snapshot.

Performance concern sent: ranking redundantly joins Decision directly and again inside the eligible-ID IN subquery. Building scores directly from the compatible eligible query joined once to DecisionEmbedding preserves every guard while avoiding a redundant Decision scan/semijoin. Correlated cross-table effective-head and Conflict lineage predicates can cause severe planner underestimates; same-table extended statistics cannot directly describe this correlation. Do not weaken lifecycle/head/lineage guards to satisfy the planner. Actual 10k EXPLAIN and a passing full concurrent-handler benchmark are still required before acceptance; no performance approval implied.

## Final single-pass CTE source follow-up (working tree after 00c770e)

Inspected the revised materialized scoped eligibility → compatible → prepared → diagnostics → scored → page flow, CASE checkpoint optimization, null-free successor exclusion, local PostgreSQL planner controls, frozen JSON fingerprint and `include_review` optimization. Parent is rerunning the required benchmark; no reviewer runtime/heavy tests executed.

**No blocking source finding in this revision.**

- Every eligibility guard remains: confirmed supported value outcome, current effective RESOLVED head, matching Conflict lineage, no successor, current actor scope, query Conflict excluded. The uncorrelated `NOT IN` explicitly excludes null predecessor values, avoiding three-valued SQL exclusion errors.
- Narrow scoped and compatible sets are materialized once. Distances are computed only for compatible cases. Actual vector presence or explicit immutable non-INDEXED skip checkpoint establishes representation coverage; absent representation without skip forces INDEXING. Missing/corrupt diagnostics suppress all page results, preserving no-silent-partial-index policy.
- Global partial-index corrupt IDs are intersected with compatible scoped IDs before affecting the response; foreign failures do not become counts/results. Counts/page/diagnostics remain under the same authenticated read-only snapshot. Empty pages preserve total count and deterministic ties.
- `SET LOCAL enable_nestloop=off; SET LOCAL jit=off` is narrowly applied to the final retrieval read transaction to avoid the observed PostgreSQL17 estimate/JIT pathology. These controls do not change authorization or business semantics and revert with the transaction. The 1500ms protective statement budget is distinct from the unchanged p95<=1s/10-session acceptance target; passing actual measurements are still mandatory.
- `fingerprint` uses the same canonical encoding as the Stage6 digest for frozen JSON primitives; a compatibility test covers JSON-encoded UUID/time/Unicode/nested primitive values. Existing Decision hashing/saves remain unchanged.
- `historical_context(..., include_review=False)` is used only by retrieval/query preparation to avoid computing an unused review token. The default remains True for Stage6 and frozen historical inputs remain unchanged.

Requested fresh affected gates after the final CASE optimization: late-commit snapshot barrier, uncertain/excluded checkpoints, below-threshold corruption, no/low history, empty offset page, regressions and full 100/1k/10k concurrency. Final exact-HEAD source/evidence review remains pending.

## Committed-source and capacity evidence review at 3defa922a72e6907aea7c1eb5cf4a02af53610b5

Read-only inspection of the committed source delta, latest tests, migration coverage, documentation and root-generated `docs/testing/reports/stage7-capacity-2026-10-23.json`. Parent reports60 similarity and49 frontend tests passed; reviewer has not independently executed these yet, because parent is rebuilding images and has reserved the shared4-CPU runtime. Worktree contains parent documentation/report changes only at this checkpoint.

**Source: no unresolved blocking architecture/security/product-intent findings. Capacity evidence: satisfies the mandatory10k persisted Decision/vector and measured10-session p95 target for this synthetic development profile.**

| persisted Decisions/vectors | concurrent requests/sessions | concurrent p95 seconds | warm p95 seconds |
|---|---|---|---|
|100/100|50/10|0.302138|0.052167|
|1000/1000|50/10|0.452128|0.096947|
|10000/10000|50/10|0.840550|0.162569|

The source benchmark asserts successful READY HTTP responses and p95<=1s, persists actual guarded Decision/vector rows, measures top1/5/20 and first-with-preparation, process RSS and relation/index sizes, and records the actual final query's EXPLAIN ANALYZE. The10k plan shows scoped effective-head hash join, compatible filtering, one metadata/vector join, exact pgvector distance, partial integrity index, diagnostics before results and bounded final page. No predicate was dropped to obtain the result. Cold OS/PostgreSQL cache and100k Decisions remain explicitly unmeasured; no semantic-quality or independent-human-workload claim is made.

Small reporting correction sent to implementer: `indexing_new_rows` is computed as newly expanded Decision count; the first cohort has99 newly expanded Decisions plus the existing unindexed seed, so it actually indexes100 vectors. The first vector-throughput numerator should be100 or the field should be named expanded Decision rows separately. This does not affect the10k capacity, latency or row counts.

Gate inventory reviewed: tests now include fresh late-commit snapshot barrier, pagination/ties/empty offset, local planner/deadline isolation, malformed input/vectors, query RQ failure/cooldown/retry, real RQ backfill recovery, interrupted migration/rollback/retry, wrong-schema vector extension migration refusal, and downgrade-with-vectors preservation. Runtime restart/production/provider/DB failures, browser/a11y/responsive, complete Stage1–6 regression/security/dependency gates and independent execution are still pending evidence review. Final exactHEAD CI and no-merge stop remain required.

## Independent execution — selected integration/migration gates

At parent's explicit isolated-fixture execution window, ran from `backend` with `/tmp/fk-stage7-dev.env`, `FK_ALLOWED_ORIGINS=["https://localhost:8443"]`, `FK_TEST_INTEGRATION=1`, `UV_CACHE_DIR=/workspace/.cache/uv`:

```text
uv run --frozen pytest -q tests/test_similarity_integration.py tests/test_similarity_migration.py -k 'real_path_new_case or superseded_and_reopened or read_permissions_are_matrix or structural_incompatibility or unrelated_real_import or snapshot_barrier or provider_crash_rolls_back or http_query_preparation or query_provider_failure or downgrade_with_vectors or empty_upgrade_downgrade'
```

**19 PASSED,19 deselected,24.19s; zero failures.** Two dependency deprecation warnings (Starlette TestClient/httpx and RQ `exc_info`) do not affect results.

Exact exercised cases:

- 1 persisted actual import→review→Decision→pgvector retrieval, read-only fact preservation/idempotent backfill;
- 1 reopened/superseded effective-head exclusion and reindex;
- 4 VIEWER/REVIEWER/DATA_OWNER/ADMIN read and immediate scope revocation;
- 6 incompatible domain/entity/attribute/conflict type/value kind/unit SQL filters;
- 1 unrelated actual imported case below threshold;
- 1 concurrent late human commit snapshot barrier (coherent old pool, next request INDEXING);
- 1 provider batch failure rollback/prior-checkpoint recovery;
- 1 no embedding in HTTP/background preparation;
- 1 real RQ query failure sanitized UNAVAILABLE/cooldown/retry recovery;
- 1 downgrade refusal with preserved populated Decision/vector history;
- 1 empty migration interrupted upgrade rollback/retry/repeat/downgrade/upgrade.

Tests used their existing disposable `auth_test_<uuid>` schemas, temporary storage and isolated queues; fixture cleanup completed. Reviewer did not mutate public runtime data, services, deployment/E2E configuration or browser state. Root integration ran concurrently in separate owned fixtures; no capacity/performance claim is derived from this shared-load selected test duration.

Execution started at3defa922a72e6907aea7c1eb5cf4a02af53610b5 and ended after parent committed3bb5542388503c3626b5ede1bac34753d4666e9c. Inspected the exact commit delta: benchmark accounting/report and documentation only; production and exercised test source is identical. Corrected capacity report now counts100/900/9000 newly indexed vectors with first throughput143.72/s. Final runtime/browser/security/regression/exactHEAD evidence remains to review before acceptance.

## Final evidence / UI / populated migration independent verification at 39fc33c21d9b6647eff00ee662cc404a11eadf59

Reviewed final local gate logs and artifact manifests, runtime/restart/cold-PostgreSQL reports, committed application delta, the added populated-history migration case and acceptance draft. No application/service/public-data mutations by reviewer.

Verified root-generated evidence:

- `check-final`:256 backend unit tests,49 frontend component tests; lint/format/mypy/build/E2E type checks pass. Gallery/documentation checks pass.
- Full integration log:507 PASS and13 real browser E2E PASS. The subsequent new migration preservation case brings unique integration coverage to508; no count of repeat runs is added to that number.
- SAST: no findings; backend/frontend SAST fixture rejection works; secret fixture rejected and history/worktree scans show no leaks; dependency audits show no known vulnerabilities.
- Gallery log:27 real screenshots,27 Axe checks,135 responsive checks, source tree match. Independently verified all27 screenshot SHA-256 values against the manifest, with no failed accessibility/responsive entry. Manifest source39fc33c, treebe3a27916937046f924c34d69ca63b4c89fd10cc, served frontend bundle and image digests recorded.
- Visually inspected screenshots24 similar precedent,25 real Decision detail/history,26 no precedent with usable Human Review,27 revoked-scope path. Cards show actual IDs, score, readable historical outcome, value/unit/actor/date/reason, concrete structured context and frozen observations. Test warning and mandatory past-experience disclaimer are prominent. No current-case answer or automatic action is proposed.
- Restart JSON source39fc33c: actual HTTPS; interrupted checkpoint1 recovered by real worker; old/new versions coexist and explicit activation changes version; duplicate delivery idempotent; PG/Redis/backend/frontend and full worker restart preserve results/facts; actual PostgreSQL stop returns sanitized503 and recovers; historical facts and old vectors unchanged.
- Cold PostgreSQL evidence source39fc33c:10k compatible Decisions, first query limit20 after owned PG process restart0.312886s; warm readings0.108–0.229s. OS cache explicitly retained; no raw cold-OS-cache or100k claim.

Independently executed only the newly added preservation case in its disposable fixture:

```text
uv run --frozen pytest -q tests/test_similarity_migration.py::test_stage7_upgrade_preserves_populated_stage2_to_6_history
1 PASSED,2.65s
```

This constructs a real Stage2–6 import→human Decision history, returns to0007 with empty derived retrieval tables, hashes every existing non-retrieval table, upgrades twice and verifies all hashes plus real Decision detail and RESOLVED Conflict. Independent targeted execution total is20 cases (19 earlier plus this1), all passing. Fixture-owned schema/queue cleanup completed; no public tables/services/deployment configuration changed.

**Conditional final verdict: PASS for product/architecture/security/source and reviewed local evidence; no unresolved blocking finding.** READY TO MERGE still requires the production smoke evidence, completed final acceptance/independent report, final commit source/artifact delta acknowledgement and successful CI for that exact final HEAD. This report authorizes no merge. Capacity source is3defa92; runtime/gallery source39fc33c (asked implementer to distinguish these in the final acceptance provenance).

## Final local acceptance — production gate completed

Inspected `/tmp/fk-stage7-production-final.log` and completed `docs/testing/reports/stage7-similarity-acceptance-2026-10-23.md`. Production gate reports all four required groups PASS: two concurrent100MB HTTPS uploads with exact checksum and temp cleanup; production HTTPS/file-secret/non-root/read-only/resource hardening; real RQ worker healthy→stale/unhealthy→stopped→restored; PostgreSQL/Redis persistence and no credential values in inspect/logs. The unique disposable production smoke is separate from preserved Stage7 business volumes. Final acceptance now correctly splits capacity/backend source3defa92 and actualHTTPS/runtime/gallery/coldPG source39fc33c.

**Final local acceptance verdict: PASS — no unresolved blocking architecture, product-intent, canonical-model, lifecycle, security, scope, retrieval integrity, API/UI, migration, runtime/recovery or capacity finding.** All earlier findings in this review were corrected and affected source/tests/evidence rechecked. Independent execution20 targeted real integration/migration cases PASS; complete root gates and final artifacts inspected as recorded above. No Recommendation Engine, AI/LLM/Qwen runtime, automatic Decision, rule mutation or write-back entered scope. Production deliberately returns honest unavailable and the separate test provider is not represented as production semantic acceptance.

The only remaining release gate is final commit/artifact delta inspection and successful CI for the **exact final HEAD** to be identified in the PR. Until that acknowledgment, this is local acceptance and not an assertion that finalHEAD CI has completed. After that gate passes, the permitted stop is READY TO MERGE; no merge or issue closure is authorized. Production semantic quality/runtime,100k actual Decisions, cold OS cache and external-site publication remain explicitly outside the proved acceptance boundary.

## Exact-HEAD CI finding — idle worker recovery delay (583717e not accepted)

Final583717e CI failed the real gallery because retrieval remained INDEXING for90s. This supersedes the earlier local-only PASS as a release verdict: **the current release gate is BLOCKED pending the idle-worker correction and affected retests/new exactHEAD CI.** No merge occurred.

Read-only investigation of pinned RQ source independently confirms the root cause. `dequeue_timeout` is `max(1,worker_ttl-15)`, therefore105s at the configured120s worker TTL. The blocking dequeue loop evaluates maintenance before blocking and after a dequeue timeout, so `maintenance_interval=30` alone does not cause recovery at30s when the queue stays empty. Earlier local gallery workloads could wake the worker with unrelated jobs and mask the idle path. New Decisions intentionally do not enqueue Redis jobs, so autoindex depends on periodic recovery.

The proposed `ForestWorker.dequeue_timeout` override capping the RQ blocking interval by `maintenance_interval` is valid and preserves all authorization/lifecycle/queue/checkpoint boundaries. Clamp the interval to at least1s to avoid Redis BLPOP0's infinite wait. RQ assigns `maintenance_interval` before connection timeout configuration calls this property, so initialization is safe. This changes only the worker wake-up cadence and derived autoindex latency; it introduces no business writes, AI, role authority or Decision-save Redis dependency. A real subprocess ForestWorker test with an empty unique queue, a subsequently committed human Decision and no unrelated job is the correct regression. Reviewer ran no tests or services during the parent's baseline reproduction. Worker health freshness may remain150s, but its old105s idle comment should be clarified.

## Idle-worker correction independent retest — 27952b9af1db2c130e1d2dd0c4fd5a54a1e57700

Reviewed the committed fix and real subprocess regression. `ForestWorker.dequeue_timeout` now returns `max(1,min(super().dequeue_timeout,maintenance_interval))`, preserving TTL limits and avoiding infinite BLPOP0. The health comment correctly describes30s idle wake-up while preserving the conservative150s heartbeat threshold. The gallery's90s bound is unchanged; it now reports HTTP status/state/reason diagnostics. No eligibility, query/API, scope, persistence or Decision-save behavior changed.

At the explicitly authorized independent window, ran against fixture-owned schema/queue only:

```text
uv run --frozen pytest -q tests/test_similarity_integration.py::test_idle_real_worker_indexes_new_decision_without_another_queue_job
1 PASSED,5.48s
```

This starts a real subprocess ForestWorker genuinely idle on a unique empty queue, then commits a human Decision and verifies its vector appears through maintenance without any unrelated enqueue. Parent also demonstrated the same case failing before the correction; reviewer independently confirmed the pinned-RQ root cause earlier. Fixture cleanup completed; no public data/service/deployment mutations by reviewer. Independent targeted total is now21 cases, all PASS.

**The idle-maintenance source finding is resolved.** Affected full integration/gallery/restart/production and new exactHEAD CI are still required before final release acknowledgment. Repeating the10k query benchmark is unnecessary solely for this polling correction: SQL/filtering/provider/cache/API and the measured capacity path are unchanged, and the existing report accurately preserves its3def source provenance. New runtime/gallery evidence should identify27952b9 or the subsequent artifact-only final commit.

## Browser synchronization review — df597af278acfebff9a4afc472c7df2d9120714b

Reviewed the test-only matching browser helper change read-only. The prior click→immediate page.goto could navigate while the logout POST was still pending, leaving the next sign-in attempt authenticated or aborting logout. The helper now waits for the actual successful POST logout response and visible login form before switching to REVIEWER/VIEWER. Existing authorization/history assertions and timeouts are unchanged; no retry, forced session deletion or application permission bypass was added. This is a valid synchronization correction, with no blocking security/product concern. Parent reports the full509 integration suite passed on the correct default provider/queue setup; fresh13-browser and affected worker/runtime/gallery/production evidence are still pending review. Reviewer ran no tests/services for this test-only delta.

## Postfix refreshed-gate evidence review at df597af278acfebff9a4afc472c7df2d9120714b

Inspected fresh gate logs read-only. Integration phase509 PASS in170.02s includes both new preservation and real idle-worker regressions. That invocation's later browser phase contained the existing logout/navigation race; the separately corrected13-browser invocation passed in1.1m. This separation is correctly recorded rather than claiming the first combined command succeeded. Fresh check pipeline passes256 unit,49 component, lint/format/mypy/build/type checks; fresh backend/frontend SAST passes.

Refreshed runtime report `stage7-restart-idle-fix-2026-10-23.json` pinsdf597af and proves actualHTTPS interrupted-checkpoint worker recovery, dual versions/activation, duplicate delivery, all-service restart with identical facts/results, actual PostgreSQL-stop sanitized503 and recovery. It uses an owned isolated schema; original public Decision aggregate fingerprints were separately compared unchanged. This preserves existing accepted business data.

Refreshed gallery log passes27 real screens,27 Axe and135 responsive checks at the unchanged90s retrieval wait. Independently rechecked all27 screenshot hashes and current committed frontend tree against the updated manifest: sourcedf597af, frontend treebe3a27916937046f924c34d69ca63b4c89fd10cc, rebuilt backend digestdc4f0004240052f32ff79eea967074383079585977c955a5cd760519b078581c. No failed gallery check or unreviewed application delta found. Existing independently inspected visual layout remains unchanged apart from actual synthetic IDs/times.

No source/security/product blocker remains. New production smoke log was still pending at this inspection; postfix local acceptance requires that outcome plus the later exact-finalHEAD CI. Existing accurately pinned10k capacity evidence remains applicable because the retrieval timed path did not change.

## Final post-fix local acceptance

Inspected the completed `/tmp/fk-stage7-production-idle-fix-final.log`: all4 production groups PASS with the corrected worker — concurrent100MB HTTPS uploads/checksums/temp cleanup; HTTPS/file secrets/non-root/read-only/resources; real RQ healthy→stale/unhealthy→stopped→restored; PostgreSQL/Redis persistence with no credential values in inspect/logs. No unreviewed application/test-driver changes exist beyonddf597af.

**Post-fix local acceptance: PASS, no unresolved blocking findings.** The genuine idle-worker defect found by583717e CI was corrected, independently source-reviewed and independently retested with a real idle process. Existing matching browser logout synchronization was reviewed without weakened assertions/timeouts. Refreshed509 integration,13 browser,256 unit,49 component/lint/format/mypy/build/types, SAST, actualHTTPS restart,27 screenshot/Axe135 responsive and production smoke evidence now passes. Previously passing secret/dependency/rejecting-fixture and accurately pinned10k capacity/coldPG evidence remains applicable; these boundaries are explicit in acceptance. Independent targeted integration/migration execution totals21 passing cases.

Decision Registry/evidence remain immutable sources of truth; scope and lifecycle policies are preserved. No Recommendation Engine, AI/LLM runtime, automatic Decision or write-back was added. The final report must preserve the failed583717e CI as historical evidence, not use it as release approval. A new artifact/report-only final commit and successful CI for its exact SHA are still required before READY TO MERGE. No merge or issue closure is authorized by this local verdict.

## Dependency gate correction after08fc40f CI

The exact08fc CI correctly stopped at dependency auditing: filelock4.1.1 was reported with6 advisories in the inspected log (CVE-2026-112906,112940,112914,112913,112937,112907), all fixed by4.2.1. Therefore08fc is historical failed CI, not release approval.

Read-only independent TOML comparison confirms the proposed lock update changes only the filelock record from4.1.1 to4.2.1 and its exact pinned PyPI sdist/wheel hashes. No package graph, manifest, application, migration or runtime configuration changes. Independently traversed the resolved runtime dependency closure: filelock is absent. Its sole chain is development-only pip-audit→cachecontrol[filecache]→filelock; both Docker build `uv sync` steps exclude development dependencies with`--no-dev`.

Fresh dependency log reports no known Python/npm vulnerabilities; fresh check log shows successful tests/build/type checks. No advisory ignore, scanner bypass, weakened test or timeout was introduced. **Minimal security dependency correction: PASS, no source/security blocker.** Existing runtime/capacity/browser evidence remains valid for unchanged application dependencies/code; a new final commit and successful exactHEADCI are required. Reviewer executed no tests, services or dependency/environment mutations for this review.
