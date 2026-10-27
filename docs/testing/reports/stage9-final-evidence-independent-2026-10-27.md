# Stage9 — independent final development-evidence review

27 October 2026. Read-only checkpoint at HEAD63fd84d plus current uncommitted test-helper, restart-probe and evidence/report delta. This is a development evidence review, not Stage9 acceptance or exact-final-artifact CI acknowledgement. Reviewer changed no source, Git, deployment or public data and repeated no inference/restart in this follow-up.

**Verdict: no new blocking source/evidence defect identified in the reviewed delta. Stage9 remains BLOCKED / NOT READY TO MERGE.** Human-approved semantic targets/labels and representative10k-real-vector / ten-session AI+core NFR remain unfulfilled; production activation and positive production policy remain disabled. Smoke/vertical success supplies no semantic quality approval.

## Source and provenance consistency

Independently verified no backend/app or frontend/src change between06959e6 and63fd84d. Current reported tested-image inventories exactly match current source bytes: all86backend Python files and16AI Python files for each model image. The inventory report describes backend imagebc5d510e, embeddingfc87b4da and LLM998a8e65. Current source equality was independently recalculated; this follow-up did not re-export image contents or rebuild/restart them. Model manifests/prompt v5/32768context/1024dimensions and demo policy are unchanged.

`backend/tests/test_recommendations_integration.py:business_hash` changes fixed table name sources to canonical source_systems, matching the ORM table declaration. This adds previously silently skipped source-system state to immutable-business comparison; it removes no assertion and changes no application behavior. The helper’s fixed table list and fixture schema scope are preserved. The change itself is a current uncommitted test delta and must be included in final checks/commit provenance rather than called already covered by older CI.

## Restart probe safety and proof limits

`backend/tests/ai_restart_probe.py` validates private fixture kind, exact auth_test schema pattern, unique stage9-ai-browser queue pattern, auth prefix equal to schema+':', and selected DSN driver/host/port/database/username before connecting to the fixture database. It then checks actual current_schema() equals the recorded owned schema. Names used in SQL are a fixed canonical list; no fixture strings are interpolated into SQL. URI/key/password/vector/prompt values are not printed. SQL only reads this owned schema. The only Redis mutation is a900-second canary under the already validated owned queue prefix, later deleted; there is no schema/drop/flush/customer-key mutation or automatic service restart in this helper.

Reads compare complete ordered table-row digests and counts, require seven Decisions and1024-dimensional embeddings, then compare the after snapshot with the recorded before snapshot. Final result reports seven actual vectors preserved, immutable business digests preserved and Redis canary preserved. Inspected successful before output, operator restart output naming only fk-stage9-postgres-1/fk-stage9-redis-1, and after-probe PASS. Root will retain a short credential-free transcript alongside the aggregate report; JSON booleans alone are not independent evidence that a restart occurred.

This is persistence proof for a quiescent legally synthetic owned fixture through an actual operator-controlled PostgreSQL/Redis restart. It does not prove power-loss durability, repeated retrieval/ranking correctness after restart, all queue/crash schedules, cryptographic authenticity or customer production restore. Actual-vector identity comes from the same actual-Qwen fixture and unchanged source/model inventory, not merely from the vector length check.

## Current acceptance evidence inspected

- Corrected local full suite log:567integration PASS,3explicitly optional actual-model tests skipped,311deselected,618.12seconds;15HTTPS browser PASS in1.1min. Skips are not labelled actual-model PASS.
- Separate actual pinned-Qwen tests:3PASS in138.61seconds. Current test source includes actual vector backfill/query/scoped lookup, shadow checkpoint/new worker/cutover/test-space rollback, and genuine Registry-to-grounded-LLM-to-human-confirmed-Decision vertical. Parent executed this run; reviewer inspected source/log, did not repeat these three tests here. Earlier independent actual2-case execution remains separately recorded in the runtime independent report.
- Corrected actual browser v2: root1PASS in2.5min. Independently recalculated all8PNG hashes against report;8Axe reports have zero violations;20responsive checks pass. Report now requires and contains flow_passed=true plus models_restored_healthy=true. Actual citation Case/Decision IDs are recorded. The previously reviewed strict cleanup ownership, nested report-finally and bounded both-model healthy restoration are present. Browser screenshots are legally synthetic and contain no login credentials/real customer payloads.
- Previous failed receipt/local/CI runs, disk-exhausted infrastructure run and v4model timeout remain historical failures. Successful current runs do not retroactively relabel them. The proven ranking-GUC restoration remains unchanged; current full regression provides broader evidence beyond the earlier isolated2-case result.

Reviewer inspected logs `fk-stage9-full-integration-corrected-ingress.log`, `fk-stage9-real-qwen-post-planner.log`, `fk-stage9-actual-ai-browser-v2.log`, `fk-stage9-actual-db-redis-restart.log` and successful before/after probe outputs. Repository artifacts reviewed include `stage9-tested-application-source-2026-10-26.json`, `stage9-real-registry-vertical-2026-10-26.json`, `stage9-actual-browser-2026-10-26/report.json` and `stage9-actual-db-redis-restart-2026-10-26.json`.

## Delivery boundary

Both63fd CI runs were reported green by root; this follow-up does not independently assert their REST status or treat them as CI for the currently uncommitted probe/test/evidence delta. Final committed-head checks and exact-SHA push/PR CI must still be recorded after aggregate documentation/artifacts are committed. No merge, issue closure, numerical-policy approval or stage progression authorization is provided. A final development checkpoint may be published honestly with its BLOCKED quality/performance status; full Stage9 acceptance is not supplied by this report.
