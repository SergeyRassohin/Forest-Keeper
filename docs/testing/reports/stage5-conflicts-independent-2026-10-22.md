# Stage 5 — independent runtime/security/product-intent review

Reviewer/session: separate Codex review session `/root`, 2026-10-22. This session did not implement Stage 5. This is independent of the author's self-review; it is not an external human audit.

Reviewed HEAD: **`d230f628c58e0d2164293549f2a5213940c0dbe7`**, [PR #22](https://github.com/SergeyRassohin/Forest-Keeper/pull/22). Includes follow-up `de3d61d` (normalization origins, counters/source-filter regressions) and `d230f62` (browser logout/retry isolation). Current main `89ee2a9` is an ancestor. The final follow-up for this review changes documentation/evidence only; exact final HEAD and CI links belong in the PR description.

## Requirements and inspected implementation

Read issue #21, especially section 27, the owner's PR #22 findings, AGENTS, canonical model/lifecycles, actual XLSX permissions, NFR, Decision Log, stage-gate checklist and Stage 2–4 documentation. Inspected conflict engine/config/models/migration, API, frozen-input pipeline, checkpoint/recovery/advisory locks, frontend, fixture/oracle and regression tests. Compared the implementation with product intent: detect/explain a problem, preserve history, keep decisions human and avoid Stage 6+ scope.

Rebuilt Docker images from the reviewed checkout and applied migration 0006 before full integration/browser testing. Actual PostgreSQL/Redis, HTTPS gateway, system Chromium and real RQ paths were used. Unit/frontend/static checks and security/dependency gates ran independently from the author. The capacity run starts from real imports in disposable schemas/queues, rather than reusing the author's prepared data.

## Executed checks

| Command / gate | Independent result |
| --- | --- |
| `bash scripts/check.sh` | PASS: 200 backend unit, 25 frontend, six artifact tests; lint, format, mypy, TypeScript, build and local document links |
| `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium bash scripts/check-integration.sh` | PASS: 437 integration/API and 11 HTTPS browser tests, migration head `0006_conflicts` |
| SAST / Gitleaks / negative security fixtures / dependencies | PASS: all four mandatory scripts; no findings/known vulnerabilities; all three unsafe fixtures rejected |
| `python scripts/check-production.py --backend-image forest-keeper-backend:latest --frontend-image forest-keeper-frontend:latest` | PASS: concurrent 2 × 100 MB uploads/checksums/temp cleanup, file secrets/non-root/read-only/resources, RQ stale/readiness/restored, PostgreSQL/Redis persistence and no credential output |
| `FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.benchmark_conflicts_quality` | PASS: four true, zero false, zero missed; VALUE_MISMATCH 1, MISSING 1, DUPLICATE 2 |
| `FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.benchmark_conflicts --records 100 1000 10000 100000` | PASS: all four profiles; [full JSON](stage5-conflicts-independent-2026-10-22/capacity.json) |
| Capacity source-filter EXPLAIN ANALYZE | PASS: both sources match all 15,000 facts, absent source matches zero; [plans/counts](stage5-conflicts-independent-2026-10-22/source-plans.json) |
| Separate 1k/source `cProfile` benchmark | PASS; profiling note below, not added to unique test count |
| Actual browser Conflict/Basis/lineage and original files after ordered restart | PASS: same two Conflict IDs/full HTTPS cards, Basis/raw/normalization/matching and original references; [restart](stage5-conflicts-independent-2026-10-22/restart.json), [physical original SHA-256](stage5-conflicts-independent-2026-10-22/originals.json) |
| Final follow-up exact-SHA GitHub Actions | Required; links/status in PR |

Unique automated tests: **679 PASS** (200 + 437 + 25 + 11 + 6), with zero failures/skips. Focused benchmarks/probes are separate evidence, not extra unique tests. The author previously reported 677 before the two new integration regressions; that historical count is not reused as the current result.

## Functional, reliability and security review

- VALUE_MISMATCH uses typed normalized values and equal canonical units, exact configured zero tolerance. Equivalent normalized mass/decimal/date values produce no false conflict; hard matching negatives do not enter business conflict generation.
- MISSING distinguishes explicit missing/null/empty from CSV/XLSX absent columns (SCHEMA_UNMAPPED), invalid/unknown/warning values and incompatible units/types. Both absent sides do not manufacture a cross-source mismatch. Original values and presence reasons remain visible.
- DUPLICATE requires a frozen confirmed MATCHED graph with multiple same-source peers. Peer IDs form deterministic evidence/dependencies; no physical merge or customer uniqueness rule is invented. Unconfirmed POSSIBLE_MATCH does not become a persisted business Conflict.
- RULE_VIOLATION and ANOMALY are canonical enums, but runtime generation is disabled without valid versioned Rules/detector. There is no AI inference or invented source precedence. LOW is an explicit neutral technical default, not a production severity claim.
- Evidence includes raw/value/entity/source/file/checksum/position links, frozen normalization/matching context, engine/config snapshot/hash, reason/presence and NOT_DEFINED authority. DB guards reject evidence/status/delete mutation. Historical input/config drift is shown without rewriting history.
- Duplicate delivery and rerun preserve immutable IDs and evidence; concurrent starts/workers serialize appropriately. Exception rollback, hard-stop checkpoint resume, failed-run retry, stale NEW recovery and real RQ execution pass. Checkpoints atomically include facts/outputs/Audit/counters. Migration 0005→0006, repeat and disposable downgrade/upgrade preserve Stage 2–4 history.
- Backend RBAC uses XLSX `conflict.view` for reads and `analysis.run` for generation. Anonymous/denied-role/Origin/session/no-store checks pass. ADMIN alone gains no business-decision authority. Browser shows both raw/normalized sides, lineage, Basis/versions and “Решение человека ещё не принято”; no Stage 6/7 action or decision endpoint is exposed.

## Owner findings — disposition

1. **Independent retest:** separate session executed the full mandatory automated/security/production set, synthetic quality, all four capacity profiles, source-filter plans and actual runtime restart. All PASS.
2. **Performance limitation:** the author's **559.070 s** at 100k/source is an engineering background/baseline batch measurement, not customer SLA or interactive/near-real-time latency. Optimization remains an open target for later stages/pilot hardening. No algorithm was changed just to improve the number.
3. **Two normalization origins:** `test_both_normalization_origins_and_source_filter` verifies both AnalysisRun IDs, source IDs, profile IDs/versions/hashes, engine versions and raw/entity associations. Detail returns both `normalization_origins`; immutable Basis retains both contexts. Browser/component tests show both origins. Singular `analysis_run_id` is the first normalization input, not the complete origin set. No destructive migration needed.
4. **Rerun counters:** `test_rerun_counters_count_outputs_without_new_rows_or_creation_audits` verifies two runs each report two outputs, with the same two immutable facts, only two creation audits and unchanged counters after duplicate delivery. `conflicts_generated` counts detected/reused execution outputs; `status_counts` is their type breakdown. API/docs/UI explicitly say this; no new-row claim remains.
5. **Source filter:** the lineage test checks either snapshot side, unknown source and combined type filters. JSONB array containment is correct; capacity query-plan evidence is collected separately before fixture cleanup.

The review found no new blocking runtime/security defect in the inspected code or completed checks. Two documentation drifts were resolved: the module map described main as Stage 0–3, and the workflow diagram sent matching review straight into Conflict Engine without distinguishing its accepted/rejected outcomes. The module map now says accepted Stage 0–4, the workflow requires MATCHED and describes implemented PR #22 separately from accepted main. No Stage 5 merge is claimed.

## Capacity, query plan and restart evidence

Linux x86_64, Python 3.13.16, PostgreSQL 17/pgvector + Redis; 2 CPU quota and 8 GiB cgroup memory limit. Full independent Import → Normalization → Matching → Conflict path in disposable schemas/queues, two sources ×30 attributes; no authored capacity input reuse. The run started on clean d230f62; subsequent worktree changes are documentation only.

| Records/source | Identities | Attributes | Conflicts | False/missed | Conflict seconds | List/card p95, 10 sessions | Peak process RSS MiB |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 100 | 100 | 3000 | 15 | 0/0 | .385 | .2287 | 162.65 |
| 1000 | 1000 | 30000 | 150 | 0/0 | 2.176 | .2681 | 190.12 |
| 10000 | 10000 | 300000 | 1500 | 0/0 | 46.600 | .4867 | 214.79 |
| 100000 | 100000 | 3000000 | 15000 | 0/0 | **361.058** | **.5589** | 791.30 |

At 100k/source: 10,000 VALUE_MISMATCH and 5,000 MISSING, exact tuple oracle PASS. Two files 30,000,381/30,105,381 bytes; import 51.732 s, normalization 345.290 s (six million values), matching 33.093 s. Peak RSS covers the whole benchmark process, including fresh Stage 2–4 preparation; it is not comparable to an engine-only replay RSS or whole deployment memory. Both 361.058 s here and the author's 559.070 s remain engineering background-batch measurements, not customer SLA or interactive latency. Early checks/profiling overlapped smaller profiles.

On the actual 15,000-row capacity dataset, SQL JSONB source containment matched all facts on either side and zero for a fresh unknown source. EXPLAIN ANALYZE of ordered first-page lookup used backward `ix_conflicts_created` index scans: .076/.066 ms for the two present sources, 15.968 ms for absent source scanning 15,000 rejected rows. These are SQL timings, not end-to-end p95; the separate metadata/card p95 above includes authenticated API sessions. A temporary read lock only delayed disposable schema cleanup long enough to capture final plans; it did not block writes. No index/algorithm change was needed for this profile.

Restart used the existing `tests.restart_conflicts` snapshot/HTTPS-card verifier with a review-local wrapper replacing its simultaneous restart call by the documented sequence: stop idle worker → restart PostgreSQL/Redis/backend/frontend → `up --wait worker`. All services returned ready. Before/after full evidence hashes and HTTPS cards match; both physical originals were read inside the backend container before/after and match stored SHA-256. No volumes or history were deleted.

Additional evidence: [synthetic quality](stage5-conflicts-independent-2026-10-22/quality.json), [instrumented profile](stage5-conflicts-independent-2026-10-22/profile-summary.json).

## Profiling note

A separate instrumented real 1k/source run used `python -m cProfile ... -m tests.benchmark_conflicts --records 1000`. `execute_conflict`: 10.204 s cumulative; 11 `process_chunk` calls: 9.993 s; ten `load_values` calls: 7.072 s cumulative (including SQL/ORM hydration and normalization metadata construction). The per-value field-selection generator ran 120,000 times and took .517 s cumulative. These are cProfile measurements with overhead and overlapping development checks, not a decomposition of the author's 559 s or a production projection.

Code inspection confirms reads are batched per 100 identities, rather than one query per identity. Each detected conflict still performs Conflict/RETURNING and Output writes plus Audit; repeated JSONB evidence has serialization/storage cost. First optimization experiment should measure/refine `load_values` hydration and repeated mapping/field resolution, then compare write batching/JSONB costs, preserving immutable evidence and atomic checkpoints. No speculative optimization is included in this review.

## Architecture / Product Intent Gate

**PASS for implemented Stage 5 scope.** Modular monolith; Web-only client; source systems read-only; no preferred/true value chosen; canonical Conflict enums with initial OPEN; technical ConflictRun reuses AnalysisRun states. Raw, normalization and matching history are retained. Forest Codex is explicitly unconfigured, release profiles are not universal truth, snapshots/lineage permit future impact lookup and explicit re-evaluation. No silent rule/reference mutation, source write-back, AI authority, Human Review resolution, Decision Registry, recommendations or other Stage 6+ behavior was added.

## Final outcome

**Independent review: PASS, no blocking findings. Technical outcome: READY TO MERGE after green exact final follow-up CI, whose authoritative SHA/links/status are recorded in PR #22.** No merge is authorized by this review. PR #22 remains separate from main; #18/#20/#21 remain open, and Stage 6 is not started. Synthetic profiles/gold do not establish industrial matching/conflict accuracy; abrupt Redis/worker stale-lease behavior remains an inherited documented limitation.
