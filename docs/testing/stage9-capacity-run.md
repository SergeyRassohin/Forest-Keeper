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
