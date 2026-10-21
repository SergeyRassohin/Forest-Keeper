# Stage 4 — separate runtime/security review, 2026-10-21

Reviewed revision: `da5c84b115373562de50bee2696eb9c5af8720aa` of [PR #15](https://github.com/SergeyRassohin/Forest-Keeper/pull/15). This is a separate Codex review session, not the implementation session and not an external human audit. No application, migration, profile or test source was changed by this review. The follow-up commit contains only documentation and measured evidence; its final SHA/CI is recorded in the PR.

## Scope and method

Read the matching engine, declarative profiles, storage loader, API/review authorization, execution/advisory locking/checkpoint/recovery code, migration guards, browser component and test coverage. Compared them against AGENTS, canonical model/lifecycles, the actual XLSX permission matrix, NFR, Decision Log and issue #14/#20. Confirmed the reviewed branch includes current main `4c03946dc7f65804da4a96b86e72fad4fabd463e` and PR #19 changes. Verified both GitHub Actions runs on the reviewed SHA are SUCCESS: [push](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39525737552), [pull request](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39525742244).

Repeated the full mandatory checks rather than treating the implementer's reported PASS as a new execution. Docker images were rebuilt from the reviewed checkout using the supported proxy/CA build adapter. Tests used local real PostgreSQL/Redis and HTTPS Chromium; capacity uses disposable schemas/queues and the real import → normalization → matching path.

## Results

| Check | Independent result |
| --- | --- |
| `scripts/check.sh` | PASS: 181 backend unit, 21 frontend, 6 artifact tests; lint, formatting, mypy, TypeScript and production frontend build |
| Integration/API | PASS: 401, including all 46 matching integration cases and Stage 2/3 regression |
| HTTPS browser | PASS: all 10 tests, including matching evidence, REVIEWER confirmation/rejection with distinct reasons, ADMIN/VIEWER restrictions, raw/normalization preservation and absent Conflict API |
| SAST / secrets / negative security fixtures / SCA | PASS: no findings or known dependency vulnerabilities; all three unsafe fixtures rejected |
| Migrations | PASS: actual stack upgraded to `0005_matching`; repeat upgrade and disposable downgrade/upgrade preserve earlier history |
| Production smoke | PASS: concurrent 2 × 100 MB HTTPS uploads/checksums; non-root/read-only/resources/file secrets; RQ healthy/stale/restored; PostgreSQL/Redis restart persistence; no credential output |
| Gold quality and offline threshold sweep | PASS: precision 1.0, automatic recall 0.8, F1 0.888889, false merges 0, unsafe automatic matches on REVIEW 0, missed true-match candidates 0 |
| Independent adversarial generation | PASS: 10,000 records/source with identical names and distinct keys; 109,000 candidates, 10,000 correct MATCHED and 99,000 NOT_MATCHED, zero false merges; largest stored bucket 33, maximum right degree 11 ≤ cap 16 |
| Capacity 100 / 1k / 10k / 100k per source | PASS: all four profiles, [full measured JSON](stage4-matching-independent-capacity-2026-10-21.json) |
| Actual browser matching history after ordered restart | PASS: unchanged full-row hashes for run, 102 candidates/pairs, two review audits, 162 raw, 660 values and six normalization runs; [JSON](stage4-matching-independent-restart-2026-10-21.json) |
| Documentation links | PASS: zero missing local targets, all 49 external HTTP links successful |

The first infrastructure attempt used the inherited running Stage 3 database, so the new health probe correctly rejected its old migration head (399 integration PASS, two infrastructure failures). Rebuilding/starting this checkout applied 0005; the repeated full integration suite passed all 401. The initial browser attempt could not launch because the expected Playwright-cache executable was absent; the documented `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium` selects the installed browser. These environment preparation failures are recorded, not counted as product PASS or silently omitted.

The additional identical-name check initially assumed no prefix-only pairs would be generated. Inspection showed the documented bounded identifier-prefix path also generates negative candidates. The corrected independent assertions require exact-key matches, reject every differing key, reconstruct confidence (.85/.35 with absent mass/date) and check both storage and degree bounds. This was a correction to the review assertion, not a product defect.

At 100k/source: 100,000 candidates instead of 10 billion Cartesian pairs, zero false merges, matching **31.294 s**, metadata p95 **0.2152 s** at ten sessions, peak benchmark-process RSS **624.32 MiB**. The real path normalized six million values from two 30,000,381-byte files; import took 36.748 s, normalization 314.755 s. Smaller profiles took .076/.432/2.870 s for matching, p95 .2227/.1901/.2095 s. Linux x86_64, Python 3.13.16, local PostgreSQL 17/pgvector + Redis, 2 CPU quota and 8 GiB memory limit. The capacity process started on a clean reviewed checkout; documentation was added afterward. Other independent checks overlapped early capacity work; these measurements are not production SLA or whole-stack memory. Oversized fallback groups correctly report coverage_limited; explicit unique keys retain all expected fixture matches.

## Architecture / Product Intent Gate

- **PASS:** sources remain read-only; raw/normalization are preserved. Matching links representations without physical entity merge/split or choosing true attribute values.
- **PASS:** only POSSIBLE_MATCH → MATCHED/NOT_MATCHED. Declared exact unique identity can auto-match only without a strong conflict; fuzzy/weighted scores never auto-confirm. Missing/invalid/unknown data does not become an exact key. Ambiguity requires review.
- **PASS:** evidence snapshots contain normalized values/value IDs, source/raw/entity/run lineage, per-signal algorithms/weights/contributions, blockers, profile/hash/engine and explicit OPEN threshold policy. Database guards protect origin/evidence and terminal results. Human actor/reason/audit remains separate from computed evidence.
- **PASS:** XLSX grants match.view to all four roles, analysis.run to REVIEWER/DATA_OWNER/ADMIN and match.review only to REVIEWER/DATA_OWNER. Backend tests check allowed/denied operations, Origin/cookie, competing reviews and terminal immutability; ADMIN alone receives no business review authority.
- **PASS:** duplicate/concurrent execution uses advisory locks and atomic 100-record checkpoints. Hard-stop resume, ordinary failure/new-run retry, late enqueue and idle-worker recovery are exercised. Bounded indices/caps report coverage limitations; omitted pairs are never declared NOT_MATCHED.
- **PASS:** historical input/profile snapshots support future Forest Codex dependency/impact lookup and explicit re-evaluation; currentness is derived without rewriting history or inventing a persisted STALE match state. Forest Codex is explicitly unconfigured; gold test labels are not a customer baseline. No silent reference/rule mutation or AI/network inference dependency was introduced.
- **PASS:** manual matching review is not Decision Registry. Stage 5 Conflict API remains absent (404); no Recommendation/Decision or Desktop Client was added.

## Outcome and limits

**Independent runtime/security review: PASS, no blocking findings. Technical outcome: READY TO MERGE once the documentation-only follow-up has green exact-HEAD CI.** All 619 automated tests passed (181 backend unit, 401 integration, 21 frontend, 10 browser, six artifact tests); additional gold/capacity/adversarial/restart and production/security checks passed. Synthetic key semantics and thresholds remain unsuitable for claiming production matching accuracy. Coverage caps and the inherited abrupt simultaneous Redis/worker restart limitation remain disclosed in the [acceptance report](stage4-matching-acceptance-2026-10-21.md).

No automatic merge. Separate Stage 4 acceptance, authorized merge and successful main merge CI remain necessary before marking the stage accepted or beginning Stage 5, per issue #20. This review does not close external MVP readiness #18.
