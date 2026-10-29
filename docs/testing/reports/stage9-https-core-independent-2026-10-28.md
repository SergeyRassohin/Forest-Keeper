# Stage9 — independent HTTPS core load during actual backfill

27 October 2026. Read-only source/evidence review of new benchmark_ai_https_core.py and its fault regressions during the ongoing owned10k Qwen backfill. Reviewer did not invoke load, inference, restart, index-driver commands or DB/Redis writes. Inspected Docker metadata/networks read-only and ran only pure mocked measuring-tool tests; no source/Git edits.

## Checkpoint verdict

One initial measuring-tool false-PASS defect was found and corrected during review. Current source has no remaining blocking ownership/security/response-validation defect identified. **20pure measuring-tool tests PASS in0.96s**:19author observer negatives plus one independently written complete mocked-main malformed200 negative. This is verification of the instrument, not actual-model/performance acceptance. Stage9 remains BLOCKED; this new helper measures one additional narrow NFR boundary only.

## Initial defect and corrected source

Initial reader set valid=true on HTTP200 before calling data.get for details. A JSON list/scalar then raised but except left valid=true, allowing malformed details to count as valid and potentially produce PASS. Revised observe validates dict/list shape and owned case/history membership, sets valid only after all checks and explicitly false on exceptions. Final gate also requires every error_code absent and exactly100samples for each of five endpoints/500total. Current19unit negatives cover all malformed detail shapes, transport/nonJSON and wrong dataset lists. The independent pure main-level case injects malformed200Decision details and checks500samples are retained with at least100invalid and reportpassedfalse; no realHTTP/SQL/model is used. Source changed before the independent simulation executed, so no independently executed pre-fix RED is claimed.

Unique new report path and initial passed=false prevent stale-success reuse. try/finally preserves partial samples and bounded exception class, without private text/body/URI logging. Atomic replacement protects report completeness. p95<=1second, zeroinvalid and unchanged business history remain required; no threshold waiver was found. Warmup/setup failures cannot pass. Ten distinct existing fixture-cookie sessions and a barrier create the stated concurrent GET load.

## Ownership/TLS/read-only boundaries

Fixed project/server/loopback URL18457; explicit owned opt-in and private fixture kind/schema/target/phase/token/query checks; backend Compose project label and actual current_schema/10000Decision probe; initial registry membership matches owned history. Fixed SELECT probe table names and UUID parameters cannot create arbitrary SQL. It reads complete canonical business digests and derived indexing counts/status, emits no raw source, vector, prompt or credential. It executes no DDL/business write and does not start/stop any service. HTTP workload has only fixed GET paths: conflicts, registry, Decision detail, review context and Conflict detail; no AI request or Decision POST.

TLS verification uses the explicit development certificate, default hostname checks, trust_env=false and no redirects; no certificate bypass. Existing HttpOnly cookie contract is reused, no bearer interface. The separate backend/frontend profile uses the same actual backend image and private selected fixture settings, with no AIworkers in that project and no public model port.

Independently inspected actual capacity backend metadata: imagebc5d510e, UID1000, read-only root and cap-dropALL; network membership exactly fk-stage9-capacity_default / fk-stage9_default / fk-stage9_ai_private. All three actual networks have Internal=true and expected Compose ownership labels. This is current-profile inspection, not proof of every possible operator-selected external network. Existing per-model no-egress/isolation proofs remain separate.

## First real observation and evidence limits

Read-only inspected first real report core-https-backfill-3b203ba30a4d417dbdcb648aacf06704.json and operator log:500requests, no per-rowerror_code, unchanged whole canonical business digests, endpoint p95conflict_list.202777s / registry.165143s / conflict_detail.148194s / review_context.154762s / Decisiondetail.114671s. Thus the initial instrument bug did not manifest as a recorded exception in this actual report. This report predates corrected response validation and must remain historical; rerun corrected helper for final provenance rather than relabel the old run.

During its5.3642s request window, actual embedding Docker CPU samples were77.09% and81.9%, with runPROCESSING and partial index264/10000before and264/10000after. The short window overlaps material embedding CPU activity; it does not prove a persisted checkpoint advanced during that window. NonzeroCPU alone is a weak general detector because health work can consume CPU: keep actual high samples and live backfill context explicit, not a blanket sustained-throughput guarantee.

This is actual TLS/nginx/deployedAPI/coreDB/Redis metadata under partial-index embedding backfill. It is not full10k-vector ranking, positive independent-provenance recommendation, simultaneousLLM latency, query-inference throughput, cold start, human semantic relevance,100kcapacity or full Stage9 acceptance. The deployed HTTPS backend has a different CPU profile from the1CPU in-process ASGI runner; preserve actual API/frontend/model images/limits, script hash and source/time/cache provenance in the corrected report/aggregate, rather than borrowing the earlier runner profile.

## Independent execution record

Pure command: PYTHONPATH=backend uv run --project backend pytest -c backend/pyproject.toml -q backend/tests/test_ai_https_core_harness.py /tmp/fk-stage9-https-core-independent-negative.py -o python_files=*.py. Result20PASS0.96s; log fk-stage9-https-core-independent-tests.log. Independent fixture script exists only under/tmp and uses synthetic UUIDs/tokens, mocked HTTP, mocked probes/Docker and temporary report files. No actual private fixture credentials were printed or mutated.

Continue the owned backfill and corrected narrow HTTP observation. No additional source blocker found after the listed fix. Actual completed10k-index measurements, full required NFR/hardware/quality approvals and final exactHEAD delivery gates remain open; no READY TO MERGE, production activation or policy approval supplied.


## Corrected actual V2 evidence acknowledgement

Independently inspected corrected-helper V2 report core-https-backfill-a12b69a303044f6a873d0a9b3f143fb0.json. All500rows are HTTP200, valid=true and error_code=null; noinvalidresponses; ten canonical business digests unchanged;10000Decisions before/after. Per-endpoint p95Conflictdetail.218458s / Registry.151417s / Decisiondetail.109818s / Conflictlist.192955s / Reviewcontext.164614s. During its5.4947s request window actual embedding CPU samples were77.00% and76.14%; actual persisted vectors advanced328→336 and run remainedPROCESSING. This corrected observation supplies both material modelCPU overlap and one observed backfill checkpoint advancement, while full10000-vector completion/ranking remains unmeasured here.

Current helper SHA256 independently calculated:84ebbf5ce924ee8e07c928be98c8f72af36e5a3ae0bd97ed4cf489be0515fc73. V2raw report SHA256 independently calculated:bc2d2a307dfc8de77a60069f8e4bbaefe44f813c1cb8ebf1b45c86ed56a27af8. Parent confirms these helper bytes were executed forV2 and is preparing a separate companion image/limits/network/source provenance artifact; raw historical reports are not rewritten. The existing actual HTTPS API profile is512MiB/no dedicated CPUquota, not the ASGI runner1CPU profile. Preserve that distinction in aggregate evidence.

**Corrected narrow gate: PASS for these actual500HTTPS core metadata requests concurrent with actual partial-index Qwen backfill in this observed profile.** This does not accept complete10k ranking, simultaneousLLM performance, semantic quality, production sizing/activation or full Stage9. Initial V1 remains historical with its known instrument bug, despite no errors recorded in that particular run. No inference/restart/load or data/source/Git mutation by reviewer.
