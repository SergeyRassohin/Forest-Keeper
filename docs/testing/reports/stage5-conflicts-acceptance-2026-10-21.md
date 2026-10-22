# Stage 5 Conflict Engine — pre-merge acceptance

PR: [#22](https://github.com/SergeyRassohin/Forest-Keeper/pull/22), refs #21/#20/#18.

**Current follow-up: independent runtime/security/product-intent review PASS, no blocking findings. Final exact-HEAD CI and separate owner acceptance remain required; see the 2026-10-22 section below.**
This is the implementation author's verification, not an independent retest.
No automatic merge; Stage 5 is not accepted and #18/#20/#21 remain open.

Runtime code under test is unchanged since `f8eefb6`; E2E selector fix is `14f838d`.
Backend app tree: `90bb17b8a703ee685c56d4ff53f16372a69a40db`.
Frontend src tree: `aefd446cf4ecae9f2c3da219faaa0765428682db`.
Later commits add test probes/evidence/docs. Final HEAD SHA and exact-head CI link/status
are recorded in the PR description after the evidence commit, avoiding a self-referential SHA.

## Implemented

- canonical Conflict enums and immutable persisted evidence;
- versioned deterministic VALUE_MISMATCH, explicit MISSING and confirmed-identity DUPLICATE;
- frozen MATCHED input association, asynchronous execution with existing AnalysisRun states;
- atomic 100-pair checkpoints, deterministic uniqueness and safe retry/recovery/concurrency;
- metadata/detail and run API, server RBAC/Origin checks, no-store;
- browser list/detail, matching → conflicts navigation, raw/normalized/source/provenance/Basis;
- migration 0006, indexes and immutable guards, technical audit and structured correlation logs.

[Semantics, limitations and commands](../../development/conflicts.md).
RULE_VIOLATION/ANOMALY enums are supported; generation is deliberately disabled pending
valid versioned rule/detector. LOW is a versioned neutral technical default, not a business
risk estimate. No Human Review business actions, Decision Registry, recommendations, AI,
write-back or Forest Codex mutation are included.

## Architecture / Product Intent Gate — self-review PASS

| Check | Evidence / conclusion |
| --- | --- |
| Product intent | Detect and explain a problem; no truth or preferred source selection. Conflict != MatchCandidate != Decision. |
| Source/read-only boundary | Only FK storage is written; no external integration/write credentials/LLM dependency. |
| Raw/provenance/history | Raw and EntityValue unchanged; snapshots reference immutable values, files/hash/position and matching origin. Guards reject evidence/status/delete tampering. |
| Canonical model/lifecycle | Exact type/status/severity enums. Conflict only OPEN; no invented business states. Technical execution reuses NEW/QUEUED/PROCESSING/COMPLETED/FAILED. |
| Identity boundary | Only frozen MATCHED candidates. Fuzzy/ambiguous pairs require existing authorized matching review; no physical merge. |
| Missing/schema semantics | Absent CSV/XLSX column differs from empty cell; invalid/unknown/warning/unmapped is not a guessed MISSING/VALUE_MISMATCH. |
| Human authority | Existing access matrix unchanged; ADMIN can run analysis, cannot make business decisions. VIEWER is read-only. |
| Forest Codex | Explicitly unconfigured; release profiles are not universal truth. Immutable input/config hashes permit impact lookup; detail marks previous-profile results. No silent re-evaluation. |
| Architecture | Modular monolith, backend client independent; Web only. Stage 6+ scope not included. |
| Drift found/resolved | Corrected missing schema vs empty-cell semantics, schema readiness revision and browser selector. No unaccepted product/architecture deviation identified. |

## Automated gates

| Gate | Result |
| --- | --- |
| `bash scripts/check.sh` | PASS: docs links, 6 artifact tests, lint/format/mypy, 200 backend unit, 25 frontend, builds and E2E types |
| `bash scripts/check-integration.sh` | PASS: 435 backend integration + 11 real HTTPS browser E2E |
| Stage 5 direct tests | 19 unit + 34 integration; included above |
| Anonymous/drift follow-up | PASS: 401, previous-profile flag, historical Basis unchanged |
| `bash scripts/check-sast.sh` | PASS |
| `bash scripts/check-secrets.sh` | PASS: Git history and tracked tree |
| `bash scripts/test-security-gates.sh` | PASS: unsafe Python/TS and synthetic token rejected |
| `bash scripts/check-dependencies.sh` | PASS: no known vulnerabilities |
| Production smoke | PASS: non-root/read-only/file secrets/resources/HTTPS, two concurrent 100MB uploads, real RQ worker failure/readiness, PG/Redis persistence and secret redaction |
| Independent review/retest | NOT RUN — mandatory merge blocker |
| Final HEAD CI | See exact SHA/status in PR; required before merge |
| Merge / merge-commit CI | NOT RUN — requires separate owner authorization after all pre-merge gates |

Total automated test count: **677** (200 + 435 + 25 + 11 + 6). Focused reruns are not
added again to that total. Evidence: [quality](stage5-conflicts-2026-10-21/quality.log),
[integration/browser](stage5-conflicts-2026-10-21/integration-browser.log),
[SAST](stage5-conflicts-2026-10-21/sast.log), [secrets](stage5-conflicts-2026-10-21/secrets.log),
[dependency](stage5-conflicts-2026-10-21/dependencies.log),
[negative gates](stage5-conflicts-2026-10-21/negative-gates.log),
[production smoke](stage5-conflicts-2026-10-21/production-smoke.log).

## Migration / reliability

Upgrade from0005, repeat upgrade and disposable-fixture downgrade/upgrade pass, preserving
Stage2 raw, Stage3 values and Stage4 matching history. No destructive backfill/merge.
Upgrade readiness requires0006. Ordinary production downgrade deletes derived conflict
history and requires a backup/operational plan; it is not an automatic rollback promise.

Duplicate RQ delivery, concurrent starts/workers, injected rollback, 100-record checkpoint
followed by exception/hard-stop, partial retry, fresh-process reads, RQ delivery and stale
NEW recovery are tested. Old facts are reused without rewriting evidence or review.

**Full runtime restart: PASS.** [Before/after evidence](stage5-conflicts-2026-10-21/restart.json):
PostgreSQL, Redis, backend, worker and frontend restarted without deleting volumes.
The same two browser-created Conflict IDs, full HTTPS cards/Basis, raw, normalization,
matching and original references are identical. [Physical file verification](stage5-conflicts-2026-10-21/restart-originals.json)
confirms both original files still match their stored SHA-256 after restart.

## Synthetic quality

[Quality evidence](stage5-conflicts-2026-10-21/quality.json): real CSV + synthetic 1C XML →
normalization → matching → conflict, followed by explicit authorized duplicate identity review.
**4 true / 0 false / 0 missed**, types VALUE_MISMATCH1, MISSING1, DUPLICATE2.
Equivalent units, invalid/unknown values and hard matching negatives produce no false conflicts.
Precision/recall1.0 describes this authored fixture only, not a production quality SLA.

## Capacity

Two source datasets, 30 attributes/record. Final100/1k/10k use the complete real import path;
100k re-evaluates the unchanged real Stage2–4 history prepared by the same capacity fixture
with the final engine/config, separate execution and exact tuple oracle. This is **not an
independent review**. The superseded initial conflict execution is excluded from acceptance.
No full Cartesian pairs are materialized; only100k MATCHED pairs and their attributes.

[100/1k/10k measurements](stage5-conflicts-2026-10-21/capacity-small.json).
[Peer query plan](stage5-conflicts-2026-10-21/peer-query-plan.json):200 raw IDs →100 pairs,
raw_a/raw_b bitmap indexes and conflict_inputs PK;2.349ms, no full pair cross join.
[100k final-engine evidence](stage5-conflicts-2026-10-21/capacity-100k.json):
100000 identities, 3000000 evaluated attributes, 15000 expected conflicts (10000 mismatch,
5000 missing), **0 false / 0 missed**. Conflict generation559.070s; metadata/card combined
p95 .2802s /10 sessions; process peak RSS150.65MiB. No processing-time SLA is invented.
These are host-Python/ASGI measurements on the shared development host, not a customer SLA.
The real 100k/source CSV imports and Stage2–4 history were reused unchanged for the final
Conflict Engine pass; their time is not claimed as a repeated final-engine import benchmark.
The superseded early execution was stopped to avoid competing load; its incomplete result
is not acceptance evidence. Its own schema, queue and temporary datasets were removed afterward.

| Records/source | Attributes evaluated | Conflicts | False / missed | Conflict seconds | Combined metadata/card p95 |
| --- | ---: | ---: | --- | ---: | ---: |
| 100 | 3000 | 15 | 0 / 0 | .967 | .9580s |
| 1000 | 30000 | 150 | 0 / 0 | 11.699 | .6889s |
| 10000 | 300000 | 1500 | 0 / 0 | 77.672 | .6456s |
| 100000 | 3000000 | 15000 | 0 / 0 | 559.070 | .2802s |

The source trees under test match the runtime tree hashes at the top of this report;
worktree/commit differences during capacity were test helpers and evidence only.

## Remaining acceptance steps

Independent reviewer must repeat #21 section27, resolve blocking findings, and validate the
final exact HEAD CI. Then obtain the owner's separate merge permission. Only after merge and
green exact merge-commit CI can Stage5 be accepted; Stage6+ is not started by this PR.

## Independent review follow-up — 2026-10-22

A separate Codex review session inspected/retested exact HEAD `d230f628c58e0d2164293549f2a5213940c0dbe7`, including de3d61d/d230f62 regressions. **679 automated tests PASS** (200 backend unit, 437 integration/API, 25 frontend, 11 HTTPS browser, six artifact tests), security/dependency/production gates PASS. [Independent report, findings, architecture gate and measured evidence](stage5-conflicts-independent-2026-10-22.md). This resolves the earlier NOT RUN independent-review checkpoint; the 677-test author record above is historical.

All owner findings were checked: both normalization origins/versions/hashes in API/Basis/UI; rerun counters count execution outputs with no extra immutable facts/creation Audit; source filter covers either side and unknown source; performance is an explicit background-batch limitation. Independent fresh 100k/source path: 100000 MATCHED identities, 3000000 attributes, 15000 expected conflicts, zero false/missed, Conflict Engine 361.058 s, metadata/card p95 .5589 s at ten sessions. Source-filter query plans pass on the 15000-row dataset.

Both the historical 559.070 s and independent 361.058 s are engineering measurements, not customer SLA or interactive/near-real-time promises. Optimization remains an open pilot-hardening target; measured profiling is in the independent report and conflicts.md. Ordered runtime restart preserves the same browser Conflict IDs/full HTTPS cards/Basis/raw/normalization/matching; both original files physically retain their SHA-256.

Independent Architecture / Product Intent Gate: **PASS**, no blocking runtime/security findings. The follow-up changes documentation/evidence only; final exact SHA and CI are recorded in PR #22. **READY TO MERGE after green final-SHA CI, subject to separate owner acceptance. No merge performed or authorized here.** #18/#20/#21 remain open; Stage 6 is not started.
