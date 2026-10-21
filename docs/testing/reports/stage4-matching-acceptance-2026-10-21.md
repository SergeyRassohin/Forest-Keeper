# Stage 4 Matching — technical validation, 2026-10-21

Scope: [PR #15](https://github.com/SergeyRassohin/Forest-Keeper/pull/15), [Stage 4 requirements #14](https://github.com/SergeyRassohin/Forest-Keeper/issues/14), first step of [issue #20](https://github.com/SergeyRassohin/Forest-Keeper/issues/20). This report records implementer validation. It does not substitute for the required separate reviewer/retest or accept Stage 4.

## Revision and integration

Runtime measured: `6669d1c357f8bdf503013b31a1138de1269a0771`, tree `d547fb806824af32a1c71e0dfa1ffc646534dd68`. This merge synchronizes original Stage 4 `e4de1ef5ff364173e206d5dbc09362881b47be19` with PR #19 `a11ee9c1ede9c71149d8bf2d6166c2ed490dbe54`, including current main `4c03946dc7f65804da4a96b86e72fad4fabd463e`. README, progress and Decision Log conflicts were resolved without removing Stage 4 safety policy, Forest Codex or Web-only decisions.

The containing follow-up commit changes documentation, evidence artifacts and the browser rejection assertion; application runtime is unchanged from the measured SHA. Its exact HEAD and final-SHA Actions links are recorded in the PR description. The runtime checkpoint already passed both [push CI](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39524085049) and [PR CI](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39524090128); these links must not be presented as final-head CI.

## Validation

| Check | Result |
| --- | --- |
| `bash scripts/check.sh` | PASS: 181 backend unit, 21 frontend, 6 artifact failure-path tests; Ruff, format, mypy, ESLint, TypeScript, build |
| `bash scripts/check-integration.sh` | PASS: 401 backend integration tests with real PostgreSQL/Redis; 10 HTTPS Chromium E2E |
| Unique automated tests across these commands | **619 PASS; 0 failed, 0 skipped**. Deselected tests belong to the other backend partition. |
| `check-sast.sh`, `check-secrets.sh`, `test-security-gates.sh` | PASS: no findings; three unsafe fixtures correctly rejected |
| `check-dependencies.sh` | PASS: pip-audit/npm audit report no known vulnerabilities |
| Docker images and Compose startup | PASS; migration head `0005_matching`, services healthy |
| Disposable production smoke | PASS: two concurrent 100 MB HTTPS uploads/checksums/temp cleanup; non-root/read-only/resources/file secrets; actual RQ worker healthy → stale/unhealthy → restored; persistence and credential-output checks |
| Gold quality benchmark | PASS; metrics below and [JSON](stage4-matching-quality-2026-10-21.json) |
| Full 100/1k/10k/100k capacity | PASS; [complete JSON](stage4-matching-capacity-2026-10-21.json), all profiles passed |
| Ordered restart of the actual browser matching result | PASS; identical full-row snapshot hashes, [before/after JSON](stage4-matching-restart-2026-10-21.json) |
| Documentation targets and active external links | PASS: zero missing files; 48 HTTP links, zero failures; model files checked separately |
| Qwen upstream identity and offline local SHA-256 | PASS: same pinned LLM/embedding revisions as manifest, all 14 local files |
| Separate independent runtime/security retest | **BLOCKED: not yet performed for this revision** |
| CI on the final PR HEAD | Evaluated separately on the exact SHA; authoritative links/status in PR description |

Browser E2E imports CSV + synthetic 1C XML, normalizes both, starts matching and shows all three statuses. It opens raw/normalized mass and provenance, algorithm/threshold context, verifies ADMIN cannot review, confirms a fuzzy candidate and rejects another candidate under REVIEWER with different reasons. Both terminal results show actor/reason; VIEWER is read-only. Before/after normalization snapshots are equal. `/api/v1/conflicts` remains 404.

Migration tests upgrade from Stage 3, repeat upgrade, and downgrade/upgrade in disposable fixtures while asserting Stage 2 raw and Stage 3 normalized history unchanged. No physical entity merge/backfill occurs. Production downgrade would delete matching history and requires a separate backup/rollback procedure.

## Gold quality and threshold policy

13 records per source, 102 generated pairs versus 169 Cartesian pairs. Profile version `1`, hash `1cf42015888e90f50277f96071c357901a50e11d6141202868864a4fb3156251`, scoring engine `fk-matching/1`.

| Metric | Value |
| --- | ---: |
| Precision | 1.0 |
| Recall of automatic matches | 0.8 |
| F1 | 0.888889 |
| False merges / rate | **0 / 0** |
| Unsafe automatic matches on REVIEW cases | 0 |
| False non-matches | 0 |
| True-match pairs missed by candidate generation | 0 |
| Review rate among generated pairs | 0.147059 |
| Candidate reduction ratio | 0.396450 |

Compared signals: 179 exact, 100 token-sort fuzzy, 85 decimal-tolerance. Lower automatic recall is intentional: the known typo case goes to human review. This small synthetic benchmark does not establish production accuracy.

Runtime policy remains `EXACT_RULES_ONLY_NO_FUZZY_AUTO`, threshold decision `OPEN`, fuzzy auto/review thresholds NULL. Only explicit unique exact identity rules without a strong conflict can auto-match. Offline sweeps at .7/.8/.9 each produced a false merge; .95 did not, but no sweep activates a runtime threshold. See [Decision Log](../../decisions/decision-log.md) and [matching specification](../../development/matching.md).

## Capacity and restart evidence

| Records per source | Generated pairs | Matching, s | Metadata p95, s | Peak process RSS, MiB | False merges |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 100 | 0.367 | 0.9046 | 161.93 | 0 |
| 1,000 | 1,000 | 0.755 | 0.5063 | 186.94 | 0 |
| 10,000 | 10,000 | 7.380 | 0.3384 | 198.90 | 0 |
| 100,000 | 100,000 | 54.093 | 0.3648 | 624.56 | 0 |

At 100k/source: 200,000 records, 6,000,000 normalized values, two 30,000,381-byte source files. Import 61.740 s, normalization 517.049 s, matching 54.093 s / 3,697.32 total input records per second. Candidate reduction 0.99999 against 10,000,000,000 Cartesian pairs. All 100,000 persisted dispositions have reason `EXPLICIT_UNIQUE_IDENTITY_RULE`; an additional read-only SQL aggregation of saved evidence observed 100,000 exact and 100,000 token-sort fuzzy comparisons. There are no rule/fuzzy automatic dispositions. [Persisted signal-count evidence](stage4-matching-capacity-signals-2026-10-21.json).

Capacity uses the real API import → normalization → matching path in isolated PostgreSQL schemas/Redis queues with SimpleWorker. Thirty attributes are normalized per record. Metadata is measured through detail and candidate-list endpoints at ten concurrent sessions. Initial smaller profiles overlapped other local checks; these are environment measurements, not a newly invented throughput SLA. Peak RSS covers the benchmark Python process, not the database or the whole deployment.

Environment: Linux x86_64, AMD EPYC 9V74 host, cgroup CPU quota 2 CPU and memory limit 8 GiB; Python 3.13.16, PostgreSQL 17/pgvector and Redis from the development Compose stack. The JSON captures the OS build and execution method. `dirty=false` records benchmark start; the later browser-test/documentation edits do not alter the measured runtime.

Oversized fallback blocks are excluded with `coverage_limited=true`; exact IDs still retain all expected pairs in these fixtures. Omission does not create NOT_MATCHED. Completed means the declared bounded search completed. See the full diagnostics rather than interpreting reduction as proof of exhaustive recall on arbitrary data.

After the browser scenario, the documented ordered restart stopped the idle worker, restarted PostgreSQL/Redis/backend/frontend, then brought the worker back healthy without removing volumes. Health returned ok. Matching run `8cd86591-fa60-439f-9551-8a34f5bd71c5`, its 102 candidates and 102 pair links, both manual-review audit events, 26 raw records, 130 EntityValues and both normalization runs had identical ordered full-row snapshot hashes before and after. This includes frozen evidence and both review reasons/actors; it is not a Decision Registry persistence claim. The JSON artifact contains the counts and all before/after hashes, without raw payloads or credentials.

## Architecture / Product Intent Gate

Implementer assessment: **PASS for the implemented Stage 4 scope; separate acceptance remains pending**.

- Forest Keeper remains a modular monolith over read-only sources with a browser client. Backend/API remains client-independent. No Desktop Client, write-back, silent learning or AI authority was added.
- Canonical MatchCandidate fields and the three canonical statuses are preserved. Technical MatchingRun/MatchingPair reuse the documented AnalysisRun lifecycle and associate immutable input/profile history; normalization runs are not reopened. Unordered pair uniqueness is scoped per execution and self-pairs are forbidden.
- Raw/provenance, Stage 3 representations and EntityValue history are retained. Evidence stores values/IDs, quality, profile snapshot/hash/version, engine, thresholds, signal contributions, blockers and computed disposition. Manual terminal transition preserves the computed evidence and adds actor/reason/audit.
- Unknown or ambiguous identity remains for review. Weighted/fuzzy score does not choose a truth value. Matching confirmation is not the future immutable business Decision Registry.
- RBAC follows the existing XLSX permissions: `analysis.run`, `match.view`, `match.review`. REVIEWER/DATA_OWNER may review; ADMIN alone and VIEWER cannot. Backend authorization and cookie/Origin checks are covered by integration tests, including concurrent terminal transitions.
- Profile evolution creates explicit new evaluations. Historical evidence is not rewritten under current criteria; API/UI exposes previous-profile context. `gold_reference_version=NULL` explicitly means Forest Codex is not configured. Synthetic gold labels do not activate a customer baseline. Full Forest Codex approval/version/impact/rollback remains in its agreed future scope.
- Duplicate/concurrent delivery, interrupted checkpoints, late enqueue, recovery and terminal immutability are covered by real DB/RQ integration tests. Candidate indices/caps bound comparisons; capacity data below does not replace these invariants.
- No Stage 5 Conflict objects, conflict routes, Recommendations or Decisions were introduced.

## Stage 4 Definition of Done and remaining gate

| #14 DoD | Status / evidence |
| --- | --- |
| 1–4: canonical candidate; exact/rule/fuzzy and evidence | PASS: models, versioned profiles, engine/unit/integration/browser checks |
| 5–8: bounded generation; statuses; hard negatives; explicit policy | PASS: cap/block tests, zero gold false merges, no fuzzy auto-match |
| 9–10: reproducible confidence and provenance | PASS: frozen signals/profile/version/inputs and immutability tests |
| 11–14: recovery; UI; RBAC; migration | PASS: integration/browser/migration suites and restart evidence |
| 15: published quality metrics | PASS: JSON and metrics above |
| 16: 100k bounded capacity | PASS: 100,000 candidates instead of 10 billion pairs; 0 false merges; metadata p95 0.3648 s |
| 17: mandatory technical/security/browser gates | PASS locally; final-SHA CI is separately recorded in PR |
| 18: independent review without blocking findings | **BLOCKED: requires a separate reviewer/retest on final revision** |
| 19: green final SHA CI | Check exact final HEAD and linked runs in PR; checkpoint CI is not substituted |
| 20: Stage 5 not started | PASS: Conflict objects/API absent |

The [2026-10-20 entry review](stage4-entry-gate-2026-10-20.md) is an architecture entry review only; it did not test this runtime. Earlier Stage 3 reviews are historical. This implementer run must not be counted as an independent retest.

**Outcome: BLOCKED for merge/acceptance until the separate runtime/security retest and final-SHA CI are confirmed.** No automatic merge. Stage 5 starts only after separate Stage 4 acceptance, authorized merge and successful main merge CI. Issues #14/#18/#20 remain open.

Known limits: synthetic profiles need a separately agreed industrial key namespace/domain; fuzzy production thresholds remain open; capped search can omit pairs and reports that limitation; embeddings/inference are absent and deterministic matching has no hidden model/network dependency. The supported restart drains work and stops the worker before Redis restarts. Abrupt simultaneous Redis/worker shutdown can retain a stale RQ hostname registration, as documented in the inherited [production restart follow-up](external-review-docs-2026-10-21.md#ci-follow-up-ordered-restart).

## Separate review follow-up, 2026-10-21

A separate Codex review session independently inspected and retested final implementation `da5c84b115373562de50bee2696eb9c5af8720aa`: **619 tests PASS**, security/dependency checks, production smoke, gold, all four capacity profiles and actual browser-result restart persistence PASS, no blocking findings. This resolves the independent runtime/security blocker recorded above; earlier pending statements describe the implementer checkpoint. [Independent report and architecture gate](stage4-matching-independent-2026-10-21.md).

Independent 100k/source: 100,000 candidates, zero false merges, matching 31.294 s, metadata p95 .2152 s at ten sessions, peak process RSS 624.32 MiB. Full evidence is linked in the independent report. Application/tests/profiles/migrations are unchanged by this documentation-only follow-up. Exact final follow-up SHA and CI belong in PR #15; reviewed implementation CI was SUCCESS in both runs.

Technical outcome: **READY TO MERGE after green final follow-up CI**; separate acceptance and authorized merge remain required. No automatic merge and no Stage 5 work. Stage 4 is not yet accepted in main; #14/#18/#20 remain open.

## Main merge gate — Stage 4 accepted, 2026-10-21

The repository owner separately accepted exact HEAD `f44e01e3889c422505e65dc7835e7641d0b2807c` and explicitly authorized merging PR #15 in [the acceptance comment](https://github.com/SergeyRassohin/Forest-Keeper/pull/15#issuecomment-6315152669) and corresponding #14/#20 instructions. PR #15 was merged as **`bea0d55c92540744657feac863084cde131a7f43`**. Its tree `8480d386f49004224fad13d04db7d6b451018454` is identical to the approved HEAD; no application/tests/migrations changed after approval.

[GitHub Actions on this exact main merge commit](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39595762080): **SUCCESS**, including the mandatory tests/security/build/migration/browser and disposable production checks. The architecture/product-intent gate and separate runtime/security review remain PASS. **Stage 4 accepted in main; issue #14 may be closed and step 1 / Stage 4 in #20 is complete.** Earlier pending statements above are historical checkpoints, superseded by this completed merge gate.

Current setup instructions now select main. Known limitations (synthetic profiles/gold, OPEN fuzzy thresholds, capped coverage, abrupt Redis/worker stale-lease limitation and absent embedding/LLM scope) remain unchanged. #18 and #20 stay open. Stage 5 was not started as part of the merge/status update and requires a separate PR.
