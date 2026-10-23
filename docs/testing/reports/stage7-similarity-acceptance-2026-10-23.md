# Stage 7 — Similar Decision Retrieval acceptance

Date: 23 October 2026, Europe/Moscow. Scope: [issue #27](https://github.com/SergeyRassohin/Forest-Keeper/issues/27).
Branch: `codex/stage7-similar-decisions`; merge base/main: `0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852`.
Capacity/retrieval request source: `3defa922a72e6907aea7c1eb5cf4a02af53610b5`.
Initial real HTTPS runtime, UI/gallery and cold-cache source: `39fc33c21d9b6647eff00ee662cc404a11eadf59` (same retrieval/API/provider code).
Later benchmark reporting correction separates newly expanded Decisions from newly indexed vectors. Final UI outcome label uses the existing human-readable labels at `39fc33c21d9b6647eff00ee662cc404a11eadf59`; retrieval/API/provider source is unchanged. Idle-worker wake-up was subsequently corrected at `27952b9af1db2c130e1d2dd0c4fd5a54a1e57700`; refreshed proof below uses `df597af278acfebff9a4afc472c7df2d9120714b`.
Final local runtime/gallery source: `df597af278acfebff9a4afc472c7df2d9120714b`; backend idle-worker fix: `27952b9af1db2c130e1d2dd0c4fd5a54a1e57700`.
Final HEAD and exact CI are recorded in the PR so this report does not claim a self-referential commit hash.

## Product, architecture and trust boundary

PostgreSQL immutable Decision Registry remains the source of truth. Retrieval returns actual historical Decision IDs and frozen evidence, never a recommended action, automatic Decision, source selection, rule mutation or write-back. No Recommendation Engine, AI/LLM/Qwen runtime, model download or external embedding API is implemented. Stage 8 is not started.

Eligible precedents are current effective SELECT_VALUE/ENTER_VALUE heads on RESOLVED Conflicts, without a successor and with valid frozen context. Reopened/IN_REVIEW, DEFERRED, INSUFFICIENT_DATA and superseded facts remain in history but cannot become active precedents. Historical actor disablement preserves the fact. Current caller permissions and explicit domain scope apply before all counts/ranking; inaccessible IDs return 404. Existing 39 permissions/XLSX are unchanged, with no ADMIN business authority added.

Migration `0008_similarity` follows `0007_decisions` and adds version/config, vector artifacts, checkpoints/runs and query cache. Existing business facts are not rewritten. PostgreSQL FK, unique Decision/version, vector 1024/nonzero/hash and append-only constraints protect representations. Empty transactional downgrade/upgrade is supported; populated downgrade refuses without destroying Decision history. The partial integrity index checks SQL row invariants before thresholding; physical disk corruption remains PostgreSQL storage monitoring's responsibility.

## Provider and retrieval contract

- Production provider is disabled and returns honest UNAVAILABLE while Human Review/Registry remain usable. This is the explicit bounded option in issue #27 §4/8, not industrial semantic acceptance.
- Test provider: `forest-keeper/deterministic-test-embedding`; exact revision SHA-256 of `test-v1` or `test-v2`; 1024 float32 dimensions; `retrieval-context-v1`; `nfc-semantic-sort-v1`. Requires explicit development/test mode, provider selection, opt-in and frozen `synthetic:true` profile. Production refuses test provider even with opt-in. Pinned future Qwen manifest is unchanged.
- Deterministic exact filters: domain, entity type, attribute, Conflict type, value kind, canonical unit. Unknown/ambiguous compatibility fails closed. Context is bounded, normalized and frozen; transient UUID/time/raw payload/reason/chosen outcome are not embedding signals.
- Exact pgvector cosine `<=>`; score clamp(1-distance,0,1), threshold inclusive≥0.85. Default top-N 5/max 20, offset ≤100, server-owned threshold. Stable full-precision distance ASC/date DESC/UUID ASC; API 6 decimals/UI 2 decimal percent.
- Cookie-only `GET /api/v1/conflicts/{id}/similar-decisions`. Authenticated read-only REPEATABLE READ begins before auth SELECT. Scoped coverage/count/rank use one snapshot; missing/corrupt coverage suppresses partial results. GET never embeds. 1500ms transaction-local statement budget, local hash-join preference/JIT off and 120 authenticated reads/minute; other API and migrations retain defaults.
- API/UI distinguish READY, NO_PRECEDENT, INDEXING, UNAVAILABLE and request failures. Actual actor/date/outcome/value/reason, score/features/context/history are visible. Opening a precedent and returning preserves the current Conflict. Explicit disclaimer: “Похожие решения показывают прошлый опыт. Они не являются автоматическим решением текущего конфликта.”
- Bounded RQ batches, advisory execution lock, durable unique checkpoints, anti-join recovery, rollback on failed batch, explicit version activation and retained old versions. Query preparation failures persist sanitized FAILED, return UNAVAILABLE, then permit bounded retry after 30 seconds. Normal GET inputs/vectors are not logged; lifecycle/configuration/security denials are audited.

## Verification record

- `bash scripts/check.sh`: PASS — doc links/gallery/model checks, Ruff/lint/format, mypy, **256 backend unit + 49 component tests**, production frontend build and E2E/gallery TypeScript checks.
- Integration phase: **509 integration tests PASS** on the standard public-schema/queue configuration, including populated Stage 2–6 migration preservation and real idle worker recovery; migration head 0008 and HTTPS readiness checked. **13 browser tests PASS** after correcting logout synchronization in the existing matching driver. Exact-final-HEAD CI repeats the complete `bash scripts/check-integration.sh` gate.
- Similarity-focused unit/integration/migration run: 60 PASS before the additional history-preservation case. Includes all 6 compatibility filters, malformed/hostile inputs/vectors, IDOR/scope/matrix negatives, repeated requests 429, local SQL timeout 503 and unchanged Registry, coherent concurrent snapshot, pagination/ties/empty offset, uncertain/skipped contexts and below-threshold corruption.
- `bash scripts/check-sast.sh`: PASS — Bandit and TypeScript security ESLint. `bash scripts/check-secrets.sh`: PASS — Git history/tracked tree. `bash scripts/test-security-gates.sh`: PASS — unsafe shell/eval/PAT fixtures rejected. `bash scripts/check-dependencies.sh`: PASS — pip/npm, zero known vulnerabilities.
- Final `bash scripts/capture-ui-gallery.sh`: PASS — **27 actual screenshots, 27 Axe checks and 135 responsive checks**, committed frontend source-tree and served-bundle provenance checked. Browser uses actual uploads/normalization/matching/human confirmation/new-case retrieval, real Decision ID/detail/actor/date/value/reason, return with score/features, unrelated no-precedent, VIEWER read and immediate scope/detail revocation. The 13 ordinary browser cases prove unavailable retrieval preserves Human Review/save/Registry and the two-reviewer 201/409 race.
- [Real HTTPS runtime/restart proof](stage7-restart-2026-10-23.json): PASS — own `fk-stage7` only; two full source pipelines, confirmed Decision, saved partial checkpoint 1, actual PostgreSQL/Redis/backend/frontend restart, worker recovery, explicit dual-version activation, idempotent duplicate delivery, full restart with identical results/facts/vectors, actual PostgreSQL-stop sanitized 503 and recovery. Synthetic business facts/volumes are retained; the owned acceptance login/session is revoked afterwards.
- Migration: empty upgrade/downgrade, interrupted transactional rollback/retry/repeat, wrong-schema pgvector refusal/retry, populated downgrade refusal and complete pre-Stage7 table fingerprints across 0007→0008/repeat all PASS. No existing Decision/source/evidence/audit history is rewritten.
- `python3 scripts/check-production.py --backend-image fk-stage7-backend --frontend-image fk-stage7-frontend`: PASS in a unique disposable production project — two concurrent 100 MB HTTPS uploads/checksums/temp cleanup, actual RQ job, healthy→stale/unhealthy→stopped→restored worker, non-root/read-only/resources, file secrets, PostgreSQL/Redis restart persistence and no credential values in inspect/logs. Only owned disposable smoke volumes were removed; previous-stage stacks and Stage 7 business volumes were preserved.
- [Independent review](stage7-similarity-independent-2026-10-23.md): **21 targeted real integration/migration tests independently PASS**, final API/UI/27 screenshot hashes/Axe/responsive/runtime/security/capacity evidence inspected without blocking findings. Exact-final-HEAD/CI acknowledgment is linked in the PR.

## Exact-HEAD CI finding and correction

CI for `583717e` failed only the gallery's unchanged 90s READY wait. RQ default idle BLPOP could last 105s with 120s TTL, delaying nominal 30s maintenance when no unrelated jobs arrived. This was a real recovery defect, superseding earlier local-only acceptance. `27952b9` caps `ForestWorker.dequeue_timeout` by the maintenance interval, minimum 1s; TTL/readiness margin and Decision-save independence are preserved. No timeout/assertion was weakened. The real idle subprocess regression failed before the fix and passed afterwards; an independent execution also passed.

`df597af` only synchronizes existing browser role changes with successful logout and the rendered login form. The old immediate navigation could cancel logout; no application authentication behavior changed.

The refreshed [isolated real HTTPS restart proof](stage7-restart-idle-fix-2026-10-23.json) passes partial backfill/recovery, dual versions, explicit activation, duplicate delivery, full service restart and actual PostgreSQL-stop recovery. Original public Decision fingerprints were checked unchanged. Updated gallery and production evidence use the corrected worker. The 10k timed retrieval path is unchanged; independent review explicitly approved carrying forward its accurately pinned source measurements.

## Capacity and limits

[Actual capacity measurements and EXPLAIN plans](stage7-capacity-2026-10-23.json), source `3defa922`, persist 100/1,000/10,000 actual immutable Decisions and vectors under enabled DB guards. Synthetic expansion copies provenance from a real imported/confirmed fixture; it does not represent 10,000 independent human approvals or semantic diversity.

| Decisions/vectors | Warm p95 | 10-session/50-request p95 | Index time |
| --- | --- | --- | --- |
|100/100 |0.052s |0.302s |0.696s |
|1,000/1,000 |0.097s |0.452s |3.921s |
|10,000/10,000 |0.163s |0.841s |40.313s |

All responses passed; concurrent p95≤1s meets the stated NFR in this synthetic profile on a 4-CPU quota shared host. Exact compatible search and the partial integrity index are visible in the 10k plan; no ANN/HNSW recall claim. Report includes top-N 1/5/20, indexing throughput, process peak RSS, artifact/Decision/B-tree sizes and first-query preparation latency. Initial failed optimization runs are not acceptance numbers. The first benchmark query does not flush OS/PostgreSQL caches. A separate [PostgreSQL shared-buffer cold measurement](stage7-cold-cache-2026-10-23.json) restarts only the owned PostgreSQL process: first top 20 query over 10k compatible Decisions **0.313s**, then top 1/5/20 warm **0.229/0.108/0.122s**. OS filesystem cache is deliberately retained on the shared host. 100k actual Decision capacity and production semantic/provider quality remain unverified.

## Merge boundary

No merge is authorized by this report. READY TO MERGE requires completed gates, independent review without blockers and successful CI for the exact final HEAD. Owner approval is required before merge; exact merge-commit CI is a later gate. Issues #27/#18/#20 remain open; full MVP acceptance and external-site publication are not claimed.
