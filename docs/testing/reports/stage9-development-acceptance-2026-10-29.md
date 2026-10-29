# Stage 9: final development checkpoint, 29 October 2026

**BLOCKED — not READY TO MERGE.** [Specification #31](https://github.com/SergeyRassohin/Forest-Keeper/issues/31),
branch `codex/stage9-local-ai`, [draft PR #33](https://github.com/SergeyRassohin/Forest-Keeper/pull/33).
Production AI and positive production policy remain hard-disabled. No merge, issue
closure or next stage. This report updates the
[27 October checkpoint](stage9-development-acceptance-2026-10-27.md); older observations
retain their original source, resource bounds and PASS/FAIL results.

## Source and behavioral boundaries

Final tested implementation: `43fcf12b334a5d457bfafbf3afe56be801d33c4b`; business
Python bytes are unchanged from `d47fa17b74f23360fb9b803b138f1efeec9dc566`.
Later report-only changes do not claim a new runtime execution. Source/hash inventories
are in [deployment provenance](stage9-profiles-v3-deployment-2026-10-28.json) and
[actual integration evidence](stage9-final-three-actual-tests-2026-10-28.json).
Pinned model files, revisions, dimensions1024, Q4_K_M/context32768, prompt and timeouts
remain unchanged. All94 deployed app Python/JSON files match the checkout.

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

[Local gate summary and retained private-log hashes](stage9-final-local-gates-2026-10-29.json)
identify the six completed command executions without publishing raw fixtures or credentials.

| Gate | Result and precise scope |
|---|---|
| Local core checks | PASS:385backend unit tests,73frontend tests; strict mypy86files, lint/types/build, model/manifest and current-source gallery checks. `bash scripts/check.sh` final isolated run exit0. |
| PostgreSQL/Redis/RQ/auth integration | PASS:568integration,3opt-in actual-model skips,385pure deselected;572.89s. `bash scripts/check-integration.sh` with explicit configured `FK_ENV_FILE`. |
| Ordinary browser regression | PASS:15tests,1.1min in the integration run. Root normal development deployment uses production/unavailable AI; this is not a rerun of the real-AI gallery. |
| SAST/SCA/secrets/negative security | All four final local scripts exit0: `check-sast.sh`, `check-dependencies.sh`, `check-secrets.sh`, `test-security-gates.sh`. Final source43fcf12; no dependency/model changes afterwards. |
| Actual final-model integration | [PASS:3tests,127.73s](stage9-final-three-actual-tests-2026-10-28.json), fresh bounded internal-only client. Actual embeddings and actual LLM, scoped reads, two-version isolation, new-worker recovery, cutover/rollback; no model-output mocks. |
| LLM timing series | [PASS:20/20completed,20timings,0failures](stage9-real-20-vertical-timing-series-2026-10-28.json); job p50/p95/max53.8491/60.8512/87.2469s. Model/prompt unchanged; series predates the two bounded performance corrections. Repeated synthetic fixture semantics and warm processes, not Gold or cold-storage quality. |
| Actual full10k index | [COMPLETED](stage9-actual-10k-index-2026-10-28.json):10000distinct real1024dim vectors and10000input hashes;1251bounded jobs;6h52m55s. Genuine distinct file rows and API fixture Decisions, no cloned vectors or history rewrite. |
| Warm ten-session ASGI | [PASS](stage9-profiles-v3-asgi-2026-10-28.json):400valid reads,20valid warmups, immutable; recommendation p95=0.868401s, all endpoints<1s. Client/application1CPU/1GiB. |
| Ten-session actual HTTPS, idle | [PASS](stage9-profiles-v3-https-idle-2026-10-28.json):500/500valid, immutable, recommendation p95=0.801118s; all endpoints<1s. |
| Ten-session actual HTTPS, LLM startup | [**FAILED**](stage9-profiles-v3-https-startup-failed-2026-10-28.json):500/500valid and immutable, recommendation p95=1.044695s exceeds1s. Process readiness23.124s, no OS cache flush. |
| Ten-session actual HTTPS, LLM inference | [**FAILED**](stage9-profiles-v3-https-inference-failed-2026-10-28.json):500/500valid and immutable, recommendation p95=1.102804s exceeds1s. [Entire HTTP window inside successful87.3997s actual LLM phase](stage9-profiles-v3-inference-overlap-2026-10-28.json), CPU activity recorded. |
| Final model isolation | [PASS](stage9-final-model-isolation-2026-10-28.json): actual pins, authenticated private RPC, non-root/read-only policy; unauthorized, external TCP/DNS and direct DB access denied; no outbound proxies. |
| Runtime/browser/restart previously exercised | Prior actual-AI8screens/light-dark/mobile/Axe and model-stop manual fallback, PostgreSQL/Redis restart with preserved Decisions/vectors/table digests, consumer isolation and process termination remain documented in the27October report. They used the explicitly recorded earlier app image; the final two performance changes do not make them fresh final-image executions. Final actual3tests and ordinary15browser tests are separate above. |
| Independent final real inference and review | [PASS:3actual tests,0skips,117.48s](stage9-independent-final-actual-and-evidence-2026-10-29.md); separate reviewer/client on29October, same committed implementation, no concurrent parent model calls. No new blocking source finding; raw sample p95, observer/deployment hashes, business digests and final report claims independently checked. This review does not waive the stated acceptance blockers. |
| Exact-final-HEAD remote CI | **UNVERIFIED / access blocked** on29October: normal configured GitHub API returns401 Bad credentials; Git remote query cannot authenticate. Earlier checkpoint CI success does not establish final report-commit CI. No final-green claim. |

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
384other tests passed; observed0.237617s. No health assertion or timeout changed. The
isolated six health tests passed, followed by a complete isolated385-unit/73-frontend
PASS. Contention is plausible but was not proved. An earlier integration invocation
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
4. **Final synchronization and CI:** independent actual inference and scoped evidence
   review have passed. Commit/push final reports, then verify both push and PR CI on that exact full
   final SHA. Current GitHub authorization failure prevents remote verification and
   delivery; local completion alone is not synchronization.

Owner approval precedes any future merge; post-merge main CI precedes issue closure.
This checkpoint authorizes neither action and does not begin Stage10.
