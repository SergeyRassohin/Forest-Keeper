# Stage 9: actual-vector capacity run

This is an **in-progress development measurement**, not accepted semantic quality,
production sizing or READY TO MERGE. It does not approve the proposed human-gold labels
or numerical thresholds. Follow [issue31](https://github.com/SergeyRassohin/Forest-Keeper/issues/31)
and preserve the [earlier evidence/limits](reports/stage9-development-acceptance-2026-10-27.md).

## Workload and proof boundaries

The owned `auth_test_…` schema imports two synthetic CSV/1C XML files, each with10020
distinct material records across20families. Normalization, matching and Conflict generation
use the actual existing pipeline.10000fixture Decisions are created through the ordinary
authorized API with an explicit **automated synthetic capacity** reason;20Conflicts stay
open as queries. There are no cloned Decisions/evidence or fabricated vectors. Exact
unique identifier prefixes keep this workload about retrieval capacity rather than
bounded fuzzy candidate omission. Matching policy/thresholds are unchanged.

These are automated test fixtures, **not10000human-reviewed business decisions**. Both
bulk source files correlate their history under Stage8 policy. This test must preserve
abstention and must never claim the independent-positive recommendation path or a
customer-representative Gold set. The earlier independent actual five-group vertical
remains separate evidence. No precision/recall quality score is calculated here.

The actual pinned Qwen embedding service computes each distinct input in bounded batches
of8through real RQ jobs. Settings injection selects only the isolated schema/queue; neither
provider nor output is mocked. The activated version, observed model configuration,
persisted vector count/dimensions and distinct input hashes are checked and recorded.
Private schema/token state is0600inside ignored `work/stage9-capacity-private`; no
automatic schema/queue/volume deletion. Backfill checkpoints survive driver interruption.
An unexpected failed run remains failed and requires diagnosis before explicit retry.

The first capacity phase measures **warm ASGI+actual PostgreSQL/Redis**:10distinct sessions,
10query cases,400requests across Conflict list, Registry list, scoped retrieval and
recommendation. Each endpoint p95 must stay≤1second, all400responses must be valid,
and immutable business digests must remain unchanged. Current model version/provider
and scoped candidate count must match the intended workload. Errors/non-JSON responses
are failed observations; partial results persist, and every new attempt first clears PASS
and archives earlier measurements. Seven simulated failure regressions check this rule.

This baseline **does not** measure HTTPS/network overhead, simultaneous model inference,
closed evaluation-set quality, cold model/OS/database caches or a supported production
AI hardware profile. It cannot close all Stage9 performance gates. Those require separately
labelled measurements, including model inference under concurrent core load.

## Owned development execution

The runner `scripts/run-ai-capacity.py` is deliberately specific to the already verified
`fk-stage9` development stack. Both fixed bridges must be internal with the correct
Compose ownership label. It refuses root and pre-existing container names; containers
have no Docker socket, model weights, whole-repository mount or general secret mount.
Only selected source/tests/dependencies/matrix/manifest, their own fixture directory and
the private model capability are mounted. Runtime proxies are empty. CPU/memory/PID,
read-only filesystem and capability restrictions remain explicit.

The private `base.env` must contain the configured **owned development** PostgreSQL/Redis
selectors plus the documented qwen-demo/test settings from [the runtime guide](../ai/stage9-runtime.md).
Do not print those selectors, commit them or copy customer credentials into the fixture.
Models must already be healthy and the ordinary backend image/development test dependencies
available. The runner records selected image/limits, host cgroup limits, source commit and
application hashes in an owned hardware inventory; a changed application/hardware profile
requires a new run. A documentation-only commit is not a hardware change.

```sh
python scripts/run-ai-capacity.py prepare --fixture actual-10k-v1 --count 10000
python scripts/run-ai-capacity.py index --fixture actual-10k-v1
python scripts/run-ai-capacity.py measure --fixture actual-10k-v1
```

Output/logs and private ownership stay under the ignored fixture directory; only reviewed sanitized evidence is
copied to reports. On an interrupted existing phase inspect its exact ownership/state,
then explicitly restart that recorded container. The normal runner refuses silent overlap.
Confirmation resumes from actual stored Decisions. Backfill resumes committed missing
items; a completed or failed status is never silently relabelled. Existing source/history
and prior reports remain intact. One private file lock prevents overlapping phases.

## Current observations, 27 October 2026

- Restored the development stack after an environment restart removed its temporary
  capability file. PostgreSQL/Redis and all data/model files were retained; a fresh private
  capability brought the same model/backend images back to healthy. Repeated model
  network/isolation probe PASS.
- First40record calibration input produced only34Conflicts due to the pre-existing
  bounded fuzzy blocks with common generated prefixes. It remains failed evidence.
  Distinct identifier/name prefixes fixed the fixture input, retaining the same strict
 40-of40assertion and existing matching policy.
- Corrected small fixture:20actual Decisions/20actual Qwen vectors. Four bounded jobs
  took19.139659/19.265353/9.434897/0.038130seconds. At the current0.75CPU embedding quota,
  a full10kbackfill is a multi-hour run. This extrapolation is not a measured throughput
  guarantee. Actual full-run observations must replace it.
- Corrected400request calibration: warm overall p95=0.877651s, worst endpoint p95=0.974084s,
  no invalid responses and immutable business hashes preserved. This20vector observation
  is **not** a10k result, a sustained production-load measurement or simultaneous model
  inference. Background10kfixture preparation was active during that calibration.
- Full10kpreparation was paused after about3700confirmed fixture Decisions when the shared
 32GiB VFS workspace filled. Only known own finished test containers, completed migration
  container and a known unused old backend image were removed after preserving state/logs;
  all business volumes, source work, model files and fixture originals were retained.
 2.4GiBfree allowed continuation from the stored rows. A700MiBheadroom guard now pauses
  preparation at checkpoints. This is a real infrastructure limitation, not a passed NFR.

Stage9 remains **BLOCKED** until all required quality/performance/release gates and exact
final-HEAD CI are complete. Production AI and positive production policy remain disabled.


## Core HTTPS during actual partial backfill, 28 October (Europe/Moscow)

[Corrected500request result](reports/stage9-https-core-backfill-2026-10-28.json),
[independent review](reports/stage9-https-core-independent-2026-10-28.md) and
[exact source/image/hardware companion](reports/stage9-https-core-provenance-2026-10-28.json).
Execution was27October UTC; the owner's date had crossed midnight. Actual TLS verification
was enabled through local nginx to a separate512MiB API container without a dedicated CPU
quota, on the same4CPU/32GiB host. This differs from the1CPU ASGI runner profile above.

Ten actual cookie sessions made500GET requests across Conflict list, Registry list,
Decision detail, review context and Conflict detail. Every endpoint had100observations,
all500were valid HTTP200, and ten canonical business-table digests remained unchanged.
Endpoint p95 ranged0.109818–0.218458s, below the unchanged1second baseline. During the
5.4947s request window actual embedding CPU samples were77.00%/76.14%; the active run
stayedPROCESSING and persisted vectors advanced328→336. There were10000Decisions,
but only a **partial** actual-vector index. No search/LLM POST was made by this load tool.
This is a short core metadata burst with real model overlap, not sustained throughput,
full10kvector search, LLM latency or industrial acceptance.

Independent review caught an instrument bug: malformed successful detail JSON could leave
a valid flag true after an exception. Explicit type/membership validation and an exception
reset now reject that case;19negative regressions PASS, plus an independent end-to-end
negative. The [initial observation](reports/stage9-https-core-initial-historical-2026-10-28.json)
remains historical under the older instrument, despite all its500rows having no recorded
error. It does not replace the corrected rerun. Raw reports are preserved without editing
their metrics. The companion hashes bind report filenames as produced during execution;
the repository copies use descriptive filenames above.


## Process startup and timing-series preparation

The known idle development LLM was restarted once while actual embedding backfill
continued. Same image, weights, context32768 and limits; no OS cache flush. The first
retained successful Docker health check was23.6161s after restart initiation. This is
one coarse process-readiness observation, not a cold-disk startup distribution or a
production guarantee. [Startup evidence](reports/stage9-llm-process-startup-2026-10-28.json).

A [500request actual HTTPS core run](reports/stage9-https-core-during-llm-startup-2026-10-28.json)
passed during that startup: endpoint p95=0.144941–0.225857s, no invalid responses or
business-history changes. Its exact request window was21:43:35.601–21:43:42.255UTC,
before the first healthy check at21:43:47.102UTC. Embedding CPU75.52% and LLM93.11% were
sampled inside the request window; the LLM activity here was **startup, not inference**.
[Observer hash/provenance](reports/stage9-llm-startup-observer-provenance-2026-10-28.json).

The first separate twenty-vertical series stopped at its own embedding preparation,
**before any LLM call**: [failed result](reports/stage9-first-concurrent-series-pre-llm-failed-2026-10-28.json),
one attempted fixture, zero LLM timings. Its separate queue shared the model with the
continuously active backfill. Runtime intentionally has one nonblocking embedding
admission slot. This is not an observed LLM timeout/latency failure. The main backfill
continues. Retry the separate series only after it finishes, without changing service
limits/deadlines, introducing provider mocks or silently erasing this failure.

```sh
python scripts/run-ai-capacity.py series --fixture real-series-v2
```

This phase is guarded until the10000-vector fixture is INDEXED. It creates a fresh
bounded operator container and runs the existing actual Registry→Qwen→groundedLLM→
explicit fixture human-confirmation vertical twenty times, each in its own disposable
schema. Settings routing is the only injection. Per-attempt logs are private; sanitized
reports remain separate. Stop on the first failure for diagnosis. Incomplete samples
cannot pass. Record both total attempts/failures and actual LLM timing denominator;
never present a single successful observation as a p95 guarantee.

For subsequent HTTPS measurement, `FK_AI_CORE_MODE=retrieval` requires the full INDEXED
fixture and validates actual model/version and10000accessible compatible candidates.
`FK_AI_CORE_REQUIRE_ACTIVITY=llm` additionally requires substantial LLM CPU within the
recorded request window; bind that window to the actual test's `llm-phase.json` before
claiming inference overlap. Default metadata mode remains distinct from ranking.
Respect the120reads/minute actor gate and900s query-cache TTL between measurement
phases; neither limit may be relaxed to obtain a pass.


Historical startup-source limitation: the companion records the then-working observer
hash4f3d1460…, but its exact source bytes were not archived at invocation. The helper
subsequently gained completed-index/activity/retrieval modes. Do not replace the historical
hash with the latest source or assert that current bytes generated that older observation.
The raw startup/HTTP measurements remain historical observations; exact-source final
acceptance requires a fresh run on the committed helper. Future HTTP runs now archive
the observer's complete source bytes by SHA256 at invocation and record that artifact in
the report. The corrected earlier V2core run is separately bound to committed27b1797
source and its original hash.


Final-source startup rerun procedure (after full indexing):

```sh
FK_TEST_INTEGRATION=1 uv run --project backend --frozen python -m tests.benchmark_ai_model_startup
```

This guarded observer refuses a partial fixture or busy LLM, archives its exact source
bytes by SHA256 before restart, records coarse readiness and preserves failure. A
parallel HTTP observation also archives its own exact source automatically. These
fresh committed-source results are required before closing the historical startup
provenance limitation. [Runtime observer independent review](reports/stage9-runtime-capacity-independent-2026-10-28.md).


### 28 October: completed actual 10k index and observer correction

The original frozen `f6fae3f` driver completed **10,000 distinct actual Qwen vectors**,
1024 dimensions, with **10,000 distinct input hashes**. Container lifetime was
2026-10-27 21:11:20.921 UTC through 2026-10-28 04:04:16.002 UTC
(6h52m55s); 1,251 bounded jobs included the final completion checkpoint.
Job p50/p95/max: 19.682228 / 21.237548 / 24.071176 seconds.
[Original index observation](reports/stage9-actual-10k-index-2026-10-28.json) preserves
its original source hash, exact model configuration and hardware. Its `passed:false`
means the separate load measurement had not passed; indexing itself is COMPLETED.
No re-embedding or business-data rewrite was needed for the observer changes below.

[First full-index measurement](reports/stage9-actual-10k-first-warmup-failed-2026-10-28.json)
is retained as FAILED: warmup query 3 returned canonical `NO_PRECEDENT / BELOW_THRESHOLD`
with zero matches and a correctly scoped 10k pool. The observer incorrectly required
READY and stopped before any timed requests. This is not a semantic-quality finding.
The corrected observer accepts either a consistent READY/MATCHES with bounded owned
results or NO_PRECEDENT/BELOW_THRESHOLD with exactly zero matches and empty results;
provider/version/count checks remain mandatory. Expected recommendation abstention
comes from that query's validated baseline (BELOW_THRESHOLD, oversized evidence, or
insufficient independent evidence for these correlated files), never a blanket allowed
reason list. Model thresholds, policy and the one-second endpoint p95 baseline did not
change. Independent review additionally reproduced false acceptance of malformed
HTTP200 ASGI list payloads. Strict list shape, distinct owned IDs and exception
fail-closed checks now cover both Conflict and Registry lists. Negative tests retain
malformed/unhashable IDs, wrong dataset, provider, pool, version and reason failures.
Both the measurement source and the HTTPS observer's shared retrieval contract source
are archived by exact SHA at invocation. Fresh actual measurements are still required.


Corrected full-index ASGI run on committed `c8e9aa0`: **FAILED** one-second
per-endpoint p95 gate. All 20 warmups and 400 timed reads were valid, with zero HTTP
failures and immutable business history. Endpoint p95: Conflict list0.168704s, Registry
list0.154624s, similar Decisions0.559988s, recommendation**1.109600s**. Aggregate
p95=0.910812s does not override the failing endpoint. This ASGI application/client
runner is explicitly capped at1CPU/1GiB, while PostgreSQL is a separate uncapped
development container. No concurrent inference occurred in the timed window.
[Preserved failed observation](reports/stage9-actual-10k-asgi-1cpu-failed-2026-10-28.json).
The ten query/session workload includes BELOW_THRESHOLD and correlated-small-pool
abstentions as well as oversized evidence; neither success nor absence proves semantic
quality. Actual deployed HTTPS/API measurements are separate and must retain their own
measured resource profile; a PASS there cannot relabel this restricted ASGI run.

Fresh committed-source observations, same actual full 10k index and fixed model limits:

- [LLM process startup](reports/stage9-llm-final-source-startup-2026-10-28.json):
  readiness PASS, 23.4531s to retained successful health check; no OS cache flush.
- [Full HTTPS during startup](reports/stage9-full-https-startup-failed-2026-10-28.json):
  **FAILED**,499/500valid, one recommendation503; recommendationp95=1.404224s.
  The enclosing HTTP window extends2.67s after first readiness; this is a startup/ready
  transition workload, not a wholly pre-ready or generation measurement.
- [Full HTTPS during actual generation](reports/stage9-full-https-inference-failed-2026-10-28.json):
  **FAILED** one-second endpoint gate;500/500valid and immutable, recommendation
  p95=1.285170s, retrieval0.809282s, other endpoints0.157–0.220s.
  [Actual successful first vertical and phase bounds](reports/stage9-first-actual-llm-overlap-2026-10-28.json)
  prove the complete enclosing HTTP window lies inside actual successful LLM inference
  (87.2469s); this does not make the failed core latency pass.
- [Source provenance](reports/stage9-actual-10k-provenance-2026-10-28.json) includes
  hashes and exact archived observer/contract bytes, closing the new run's provenance
  gap without rewriting historical observations. [Resource checkpoint](reports/stage9-post-index-resource-2026-10-28.json)
  separates lifetime cgroup memory high-water from per-phase RSS; these are development
  measurements, not a supported production AI profile.

The twenty-observation genuine-model series is running separately; no completed-series
percentile or semantic-quality claim exists yet. The slow recommendation path requires
profiling after the frozen series completes. Previous FAIL observations stay FAILED.
