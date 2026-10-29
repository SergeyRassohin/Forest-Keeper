# Stage 9: development verification, 27 October 2026

**BLOCKED — not READY TO MERGE.** Separate branch `codex/stage9-local-ai`,
[draft PR #33](https://github.com/SergeyRassohin/Forest-Keeper/pull/33),
[specification #31](https://github.com/SergeyRassohin/Forest-Keeper/issues/31).
No merge, production activation or next-stage acceptance. Stage 0–8 main baseline is
`54d3939d704bfe6aa1c943bef3e70b83b01c0527`. Evidence filenames dated26October preserve
the original UTC run date; this summary uses the owner's Europe/Moscow date.

## Implemented behavior and intent gate

The opt-in local CPU profile runs the exact pinned Qwen3-Embedding-0.6B/1024dim and
Qwen3-8B-GGUF/Q4_K_M/context32768, without model downloads at runtime. Model files,
native source/binaries, dependency locks, prompt and schema digests are verified.
Weights, customer data and service keys are outside Git/images. Private model services
have no public ports, database credentials, tools or direct source access.

Bounded background jobs build a separate versioned Qwen index without holding SQL
connections across inference. Scope/compatibility precede ranking. Shadow backfill,
partial-coverage refusal, new-worker resume, explicit cutover, coexistence and rollback
preserve immutable history. Redis admission limits remain8global/1actor; derivation
queues are separate from core processing. Timeout/cancellation faults admission and
the supervisor kills its owned native computation; Docker restarts the model service.

The browser explicitly requests an optional ephemeral explanation. Current actor/session,
permissions, scope, evidence/version freshness and output citations are validated again
before delivery. The model selects bounded grounded clauses from authorized normalized
comparison/precedent facts; the server validates and renders the result. It cannot invent
a business action. Stage8 deterministic policy remains authoritative. No automatic Decision,
Rule, CustomerTemplate/Forest Codex mutation, source write-back or confidence-based approval.
Only a separate human submission writes a Decision. ADMIN alone gains no business authority.
Production AI and positive production recommendations remain hard-disabled.

## Executed checks

| Gate | Observed result | Scope and evidence |
|---|---|---|
| Core checks | PASS:311backend unit,73frontend; build/types/lint/strict mypy86files | `bash scripts/check.sh`; exact-source gallery guard PASS |
| Full PostgreSQL/Redis/RQ/auth regression | PASS:567integration,3optional actual-model skips,311unit deselected,618.12s | `bash scripts/check-integration.sh`, after planner and bounded test-ingress corrections |
| Ordinary HTTPS browser regression | PASS:15tests,1.1min | Same full integration command; normal production/unavailable AI configuration |
| Actual pinned-model integration | PASS:3tests,138.61s, separate opt-in execution | Real embedding→pgvector→scoped retrieval; actual LLM vertical; dual-index/recovery/rollback. Not CI mocks |
| Actual Registry vertical | PASS:5actual vectors,5precedents, valid citations, zero AI business writes, explicit human confirmation | [Measured vertical](stage9-real-registry-vertical-2026-10-26.json): backfill13.4346s,LLM95.0228s,total115.4705s |
| Actual AI browser/fallback | PASS:1scenario,2.5min;8screens,8zero-Axe checks,20responsive checks | [Report/screens](stage9-actual-browser-2026-10-26/report.json): real Qwen, actual cited Decision, human save, both models stopped/manual save, both restored healthy |
| PostgreSQL/Redis restart | PASS:7Decisions,7actual1024dim vectors, whole owned-table digests and Redis canary preserved | [Report](stage9-actual-db-redis-restart-2026-10-26.json), [operator transcript](stage9-db-redis-restart-transcript-2026-10-26.txt) |
| Model isolation | PASS:actual private/keyed RPC, no public TCP/DNS/direct DB, non-root/read-only and exact mounts | [Model report](stage9-model-isolation-2026-10-26.json) |
| Dual-network consumers | PASS:backend and both AI workers, exact two internal bridges, denied external TCP/DNS, empty proxies | [Consumer report](stage9-consumer-isolation-2026-10-26.json) |
| API/resource/security regressions | PASS:10actual DB/Redis/auth tests with explicitly stubbed model; independent36pure/process/negative tests | Scope revocation during generation/delivery, actor-session IDOR, malicious citations/cache, cancellation, concurrent language idempotency, bounded body/Origin and owned native-process termination. These are not real-model adversarial quality results |
| UI gallery | PASS:124real PNG/Axe,310responsive checks | Committed ordinary gallery and current-source guard; actual AI screenshots are separate above |
| SAST/SCA/secrets/unsafe fixtures | PASS at reviewed checkpoint; repeated by exact-HEAD CI | Bandit/TypeScript security, Gitleaks history+tracked tree, pip-audit/backend+49AI lock packages, npm audit; no known reported dependency vulnerability at scan time |
| Independent verification | Positive source/runtime review, no unresolved source blockers at checkpoint | [API](stage9-api-independent-2026-10-26.md), [runtime/actual inference](stage9-runtime-independent-2026-10-26.md), [planner/browser](stage9-planner-browser-independent-2026-10-26.md). [Final evidence follow-up](stage9-final-evidence-independent-2026-10-27.md) confirms current probe/source/artifact consistency |
| Exact final commit CI | Check exact SHA in PR #33; never infer from an ancestor | Both checkpoint `63fd84d011ca896f05e5711c781b98fd28cde541` runs [push40388986701](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40388986701) / [PR40388994441](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40388994441) SUCCESS. Later documentation/test-helper commits require their own CI |

Actual inference used legally synthetic, isolated own-file Registry fixtures with genuine
persisted IDs. They are not customer data or human-approved Gold. Settings selection in
actual tests is injected only to route to the isolated profile; model generation is real.
The [source/image inventory](stage9-tested-application-source-2026-10-26.json) verifies
running backend and both model containers' application Python bytes against this branch.
Application source is unchanged since06959; later changes stabilize test observation and
test ingress, add owner-review outlines and preserve evidence. Ordinary CI deliberately
skips optional heavy real-model tests; their separate actual execution is recorded above.

Browser draft preservation is proved across AI updates and theme changes. Navigating to
Registry follows the existing navigation behavior; this report makes no draft-preservation
claim across leaving the review screen. The restart probe proves persisted rows/digests
and a Redis AOF canary, not semantic quality or general disaster recovery.

## Failed runs and corrections retained

- Initial real-model prompt attempts failed; [initial raw observations](stage9-initial-real-models-2026-10-26.json)
  preserve those failures. The isolated v4 Registry attempt
  [FAILED at118.1443s LLM deadline](stage9-v4-registry-timeout-failed-2026-10-26.json).
  Native computation was actually stopped and its container restarted. v5 removes duplicate
  server-only identifiers while retaining current comparison and precedent facts. Context,
  output256token cap and118/120s deadlines were not increased.
- A native rebuild exhausted the32GiB VFS workspace and interrupted integration. Cleanup
  was limited to generated caches/known own unused images; business volumes and weights
  were retained. This interrupted run stays failed, not accepted evidence.
- A subsequent queue smoke used a hardcoded queue. It now uses Settings.import_queue_name;
  existing assertions remain. A later receipt run and old PR CI failed with503timeout.
- A deterministic regression proved retrieval leaked `enable_nestloop/jit` hints into its
  caller's Decision transaction. The fix restores exact caller values after fetching the
  bounded ranking page; all four initial combinations pass. No scope/policy/deadline
  relaxation. Full local regression and both63fd84dCI now pass; older failures stay failed.
- A20request Redis WATCH race needs40connections. The initial development-only relay cap32
  caused transport disconnects; its explicit cap/backlog is now128. AI capacity remains8.
- A pure process-observer test raced with already reaped descendants. It now treats only
  missing/reaped processes as dead and publishes its child PID file atomically. The same
 5second termination bound and live-process assertions remain in force.
- Early restart-probe setup attempts used a noncanonical table/function search path and
  failed before recording a baseline/restarting anything. The successful probe uses
  `source_systems` and `public.vector_dims`; failed setup is not a recovery pass.

## Unmet acceptance gates

1. **Human-approved independent semantic benchmark and numerical targets.**
   [Owner review](../stage9-owner-review.md) proposes95%returned precision/90%recall/zero
   no-match false positives or harmful outputs, but these values are not approved.
   The200candidate outlines have blank human-label fields; they are not200materialized
   histories, an independent sealed evaluation set or an approved Gold Reference.
   No semantic quality score or production-quality claim is permitted from these outlines.
2. **Representative real-vector NFR/hardware acceptance.** No accepted10kreal Qwen-vector
   benchmark/10sessions, cold/warm distributions, sustained queue throughput or supported
   hardware sizing. This4CPU/32GiB development host has noGPU. Individual real LLM samples
   (59.2815s/93.1682s/95.0228s) are not p50/p95; they have different cache/load conditions.
   [Memory sample](stage9-resource-sample-2026-10-26.json) is one observation, not a sizing
   guarantee. No100k/GPU/industrial-capacity claim. Earlier Stage8 synthetic capacity does
   not satisfy this gate.
3. **Production deployment/quality and signed distribution.** Verified local SHA files
   are not supplier signatures. Signing/offline installer/update chain is the explicitly
   bounded unresolved [dependency#32](https://github.com/SergeyRassohin/Forest-Keeper/issues/32).
   Current no-egress Docker runtime is development evidence, not a customer installation
   or accepted production AI hardware profile. Positive production policy needs its own
   explicit versioned approval after quality/safety evaluation.

These limits remain visible even with green exact-final-HEAD CI. Stage9 and external MVP
readiness are not accepted; #17/#18/#20 stay open. No new stage is started.
