# Stage 9: final development checkpoint, 29 October 2026

**BLOCKED — not READY TO MERGE.** [Specification #31](https://github.com/SergeyRassohin/Forest-Keeper/issues/31),
branch `codex/stage9-local-ai`, [draft PR #33](https://github.com/SergeyRassohin/Forest-Keeper/pull/33).
Production AI and positive production policy remain hard-disabled. No merge, issue
closure or next stage. This report updates the
[27 October checkpoint](stage9-development-acceptance-2026-10-27.md); older observations
retain their original source, resource bounds and PASS/FAIL results.

## Source and behavioral boundaries

The full10k performance measurements and first final actual-model executions used
`43fcf12b334a5d457bfafbf3afe56be801d33c4b`, whose business Python bytes were unchanged
from `d47fa17b74f23360fb9b803b138f1efeec9dc566`. A subsequent concurrent POST admission
fix is committed as `9971e94d1efee899b06d0342ef4838f7b759b7f4`; its separate regression
is described below. Historical measurements are not relabelled as new-image executions. Source/hash inventories
are in [deployment provenance](stage9-profiles-v3-deployment-2026-10-28.json) and
[actual integration evidence](stage9-final-three-actual-tests-2026-10-28.json).
Pinned model files, revisions, dimensions1024, Q4_K_M/context32768, prompt and timeouts
remain unchanged. All94 deployed app Python/JSON files matched the measured43fcf12
snapshot. The performance API retains that image; the later admission-only source delta
is not part of its recorded GET latency measurements.
[Current94-file source comparison](stage9-watched-admission-source-provenance-2026-10-29.json)
confirms only `ai/admission.py` differs; warm cached ranking/recommendation source files
and validation logic are unchanged. A GET with a missing query vector does enqueue
background query preparation through the fixed admission helper. That cold-enqueue
path changes; no synchronous inference is added and no cold latency PASS is claimed.

Two profiled performance corrections preserve business behavior: exact canonical hashes
for already-frozen JSON (legacy fallback retained), and one immutable approved-profile
digest snapshot per evaluation, reloaded on the next evaluation. Independent review,
compatibility oracles, all10000 persisted context/evidence hash comparisons and the
new two-request integration test cover these changes. No global stale cache, new policy,
SQL hint, state transition, authorization exception or deadline increase was introduced.

Stage8 policy remains authoritative. Scope/compatibility/version freshness is checked
before ranking, before model input and before delivery. AI explanation is ephemeral,
grounded and optional; only a separate authorized human submission saves a Decision.
There are no autonomous Decisions, Rule/CustomerTemplate/Forest Codex updates, source
write-back, external model calls or new end-user bearer interface. ADMIN alone has no
business Decision authority. Model failure leaves manual review available.

## Executed verification

[Final9971 local gates and retained private-log hashes](stage9-watched-admission-local-gates-2026-10-29.json)
identify the six repeated completed executions without publishing raw fixtures or credentials.
The [earlier43fcf12 gate summary](stage9-final-local-gates-2026-10-29.json) is retained separately.

| Gate | Result and precise scope |
|---|---|
| Local core checks | PASS:385backend unit tests,73frontend tests; strict mypy86files, lint/types/build, model/manifest and current-source gallery checks. `bash scripts/check.sh` final isolated run exit0. |
| PostgreSQL/Redis/RQ/auth integration | PASS on9971:570integration,3opt-in actual-model skips,385pure deselected;619.40s. `bash scripts/check-integration.sh` with explicit configured `FK_ENV_FILE`. Earlier43fcf12 run568PASS is preserved. |
| Ordinary browser regression | PASS:15tests,1.1min in the integration run. Root normal development deployment uses production/unavailable AI; this is not a rerun of the real-AI gallery. |
| SAST/SCA/secrets/negative security | All four repeated local scripts exit0: `check-sast.sh`, `check-dependencies.sh`, `check-secrets.sh`, `test-security-gates.sh`. Business source9971; no dependency/model changes afterwards. |
| Actual final-model integration | [PASS on9971:3tests,116.33s](stage9-watched-admission-actual-tests-2026-10-29.json), fresh bounded internal-only client. Actual embeddings and actual LLM74.9422s, scoped reads, two-version isolation, new-worker recovery, cutover/rollback; no model-output mocks. [Earlier43fcf12 actual execution](stage9-final-three-actual-tests-2026-10-28.json) retains its127.73s/source. |
| LLM timing series | [PASS:20/20completed,20timings,0failures](stage9-real-20-vertical-timing-series-2026-10-28.json); job p50/p95/max53.8491/60.8512/87.2469s. Model/prompt unchanged; series predates the two bounded performance corrections. Repeated synthetic fixture semantics and warm processes, not Gold or cold-storage quality. |
| Actual full10k index | [COMPLETED](stage9-actual-10k-index-2026-10-28.json):10000distinct real1024dim vectors and10000input hashes;1251bounded jobs;6h52m55s. Genuine distinct file rows and API fixture Decisions, no cloned vectors or history rewrite. |
| Warm ten-session ASGI | [PASS](stage9-profiles-v3-asgi-2026-10-28.json):400valid reads,20valid warmups, immutable; recommendation p95=0.868401s, all endpoints<1s. Client/application1CPU/1GiB. |
| Ten-session actual HTTPS, idle | [PASS](stage9-profiles-v3-https-idle-2026-10-28.json):500/500valid, immutable, recommendation p95=0.801118s; all endpoints<1s. |
| Ten-session actual HTTPS, LLM startup | [**FAILED**](stage9-profiles-v3-https-startup-failed-2026-10-28.json):500/500valid and immutable, recommendation p95=1.044695s exceeds1s. Process readiness23.124s, no OS cache flush. |
| Ten-session actual HTTPS, LLM inference | [**FAILED**](stage9-profiles-v3-https-inference-failed-2026-10-28.json):500/500valid and immutable, recommendation p95=1.102804s exceeds1s. [Entire HTTP window inside successful87.3997s actual LLM phase](stage9-profiles-v3-inference-overlap-2026-10-28.json), CPU activity recorded. |
| Final model isolation | [PASS](stage9-final-model-isolation-2026-10-28.json): actual pins, authenticated private RPC, non-root/read-only policy; unauthorized, external TCP/DNS and direct DB access denied; no outbound proxies. |
| Runtime/browser/restart previously exercised | Prior actual-AI8screens/light-dark/mobile/Axe and model-stop manual fallback, PostgreSQL/Redis restart with preserved Decisions/vectors/table digests, consumer isolation and process termination remain documented in the27October report. They used the explicitly recorded earlier app image; the final two performance changes do not make them fresh final-image executions. Final actual3tests and ordinary15browser tests are separate above. |
| Independent final real inference and review | [PASS on9971:3actual tests,0skips,107.72s](stage9-watched-admission-independent-actual-2026-10-29.md); separate reviewer/client, all86app hashes unchanged before/after, no concurrent parent inference. [Earlier43fcf12 independent review](stage9-independent-final-actual-and-evidence-2026-10-29.md) retains its117.48s and independently recomputed performance/source evidence. No new blocking source finding; these scoped gates do not waive acceptance blockers. |
| Exact-final-HEAD remote CI | **PENDING final commit verification.** Temporary29October API401/Git authentication failure recovered; checkpoint5b17f29 and fix9971e94 are pushed, PR33 remains open/draft. Historical43fcf12 CI failed the health wall-clock observer and concurrent-language admission test; 5b17f29 PR CI repeated the health observer failure. The corrections below preserve those failures and runtime limits. Earlier checkpoint CI success does not establish final report-commit CI. |

The final HTTPS samples each contain100observations per endpoint, ten existing
cookie-authenticated sessions and real scoped10k ranking. Two source files correlate
the fixture: two timed queries are below threshold, seven abstain for insufficient
independent evidence and one exceeds the evidence window. These results do not prove
independent positive recommendations or semantic accuracy. Detailed resources,
source snapshots, observer checks and failure history are in the
[capacity runbook](../stage9-capacity-run.md).

## Failures retained and actual resource limit

Earlier original/v2 latency FAILs are preserved, not averaged into the final PASSs.
The final startup/inference FAILs remain blockers. All app/model thresholds,118s LLM
deadline,1.5s retrieval budget, one-second per-endpoint NFR, rates and TTLs are unchanged.

The first final core-check run failed a strict0.1s health deadline under local load:
384other tests passed; observed0.237617s. At that checkpoint no health assertion or
timeout changed. The isolated six health tests passed, followed by a complete isolated
385-unit/73-frontend PASS. Contention is plausible but was not proved. Later CI failures
prompted the causal observer correction below; the new complete385/73run also passes.
An earlier integration invocation
selected the wrong environment file and failed DB authentication; the explicit configured
file selection fixed the setup, followed by the full568-test PASS. These failed raw
runs remain in ignored operator evidence; they are not counted as successful executions.

An offline source-image assembly initially failed file permissions before API startup;
a stale owned TLS relay target also failed its health precheck after frontend IP change.
Both development setup failures were preserved and corrected before timed HTTP runs.
The generated source context now follows standard Dockerfile code permissions. No
customer data, weights, credentials, raw pytest fixture output or private env files
are published. Business volumes and the original10kfixture remain intact.

Measured host:4CPU/32GiB,32GiB VFS Docker disk, no GPU. API512MiB/no explicit CPU quota;
embedding0.75CPU/6GiB; LLM2CPU/16GiB; PostgreSQL separate/uncapped. The supported claim is
a **limited development demonstration**, not a supported production ten-session AI
profile. No8CPU,100k or GPU capacity is measured or guaranteed. Per-process RSS and
cgroup current/lifetime peaks are distinguished in the
[memory observation](stage9-actual-inference-memory-2026-10-28.json), not summed into
a physical-RAM sizing guarantee. The source overlay is a development artifact, not
proof of signed offline customer installation.

## Outstanding acceptance

1. **Performance:** loaded startup/generation endpoint NFR fails on this profile.
   A supported AI hardware profile requires its own measured passing workload; idle
   success and LLM timing-series success cannot waive these failures.
2. **Human-approved independent Gold and preapproved targets:** still absent. The
   [200candidate outlines](../stage9-owner-review.md) have blank human labels, no
   approved semantic thresholds or sealed holdout. No precision/recall/quality score
   may be invented. Approved labels, provenance/family separation and target versions
   must precede semantic scoring; dataset changes preserve old versions/results.
3. **Production quality/policy and signed distribution:** still blocked.
   [Dependency#32](https://github.com/SergeyRassohin/Forest-Keeper/issues/32) is bounded
   but unresolved; SHA validation is not a supplier signature. Positive production
   recommendations require separate explicit policy approval after quality/safety
   acceptance. #17/#18/#20 retain their own DoD and stay open.
4. **Final synchronization and CI:** push final reports and verify both push and PR CI
   on that exact full final SHA. The temporary GitHub authorization failure recovered;
   source9971push CI40892717583 succeeded, but its PR CI failed as preserved below.
   The report commit needs its own runs; final exact SHA/CI links are recorded in
   [PR33](https://github.com/SergeyRassohin/Forest-Keeper/pull/33) after observation.

## Subsequent concurrent-admission correction

Live CI revealed a real Redis WATCH interleaving: a competing request creates the same
job after the missing-job read; the loser then sees a busy actor/full queue and refuses
before EXEC can detect dirty reads. It returned503 instead of comparing the already
bound language and returning409 for reuse. Commit9971e94 validates WATCH with an empty
EXEC before either refusal. Dirty reads retry and discover the immutable winner record.
No extra job/lease or winner-language overwrite is allowed;8global/1actor limits remain.
Two deterministic actual-Redis cases reproduced AI_ACTOR_BUSY/AI_QUEUE_FULL before the
fix. The strengthened regression uses a Russian winner and English loser, asserting
the unchanged Russian record and one job/reservation (eight only in the full-queue case).

The unrelated health unit observer previously timed TestClient/scheduler overhead against
0.1s; CI observed0.145992/0.131985s. The replacement holds the dependency on an Event,
observes **real** asyncio calls with the same configured0.02s timeout for both probes,
and requires503/database-unavailable before dependency completion. Cleanup releases the
Event inside the TestClient context. Production health code is unchanged. This causal
deadline test is not a new wall-latency benchmark and does not weaken the1s endpoint NFR.
Independent6health+5actual Redis admission tests PASS; full regression and actual-model
source verification are repeated before the final report commit. Full570integration,
15browser,385unit/73frontend and six local security/core gates on9971 now PASS; the
parent's new actual-model3tests also PASS. Independent real inference repeats all3tests:
107.72s, zero skips, actual grounded LLM65.1564s, five real vectors, no AI business writes
and separate fixture-human confirmation. These samples are not new latency percentiles
or a human Gold evaluation.
[Independent correction review](stage9-watched-admission-health-independent-2026-10-29.md)
records the real Redis interleaving, winner-language preservation and real timeout
observation, with the original failed-run hashes and unchanged runtime bounds.

Two other9971PR CI failures remain in
[preserved CI observations](stage9-intermediate-ci-failures-2026-10-29.json): normalization
concurrent start returned QUEUE_UNAVAILABLE from the recovery catch, and the profile
snapshot API exceeded its unchanged1.5s budget. Their underlying causes are unproved;
the PG statement-timeout lines in that log are intentional negative-test pg_sleep SQL.
They are not relabelled flaky or waived by the complete local PASS. Test-only observers
now attach exception class/SQLSTATE/safe callsites for a recovery failure and safe
deadline callsites/lateness for a profile failure, then re-raise the same exception.
No exception text, SQL, bind values, prompts or credentials are recorded; assertions,
concurrency and budgets are unchanged. Both instrumented targets PASS locally in8.23s;
that isolated run does not reproduce the module's aged state or erase the CI failures.
The final report HEAD requires its own full remote CI result.

Owner approval precedes any future merge; post-merge main CI precedes issue closure.
This checkpoint authorizes neither action and does not begin Stage10.
