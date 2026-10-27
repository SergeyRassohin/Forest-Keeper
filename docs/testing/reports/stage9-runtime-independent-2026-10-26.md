# Stage 9 — independent supervisor, isolated profile, native cache and v5 review

26 October 2026. Read-only review at a404d1f plus its current explicitly uncommitted runtime/cache/prompt/test/documentation delta. This is a checkpoint review, not exact-final-HEAD acceptance. No application, Git, public data, model/service restart or deployment configuration changes by reviewer. Parent explicitly authorized repeating the dedicated real-acceptance container, whose tests create disposable schemas and queue namespaces.

## Source verdict

No new blocking architecture/security defect found in the reviewed supervisor/profile/native-cache/loopback-ingress/minimal-prompt changes. This does not close the remaining Stage 9 acceptance gates.

- `backend/app/ai/supervisor.py` owns only process groups it created with fixed argv and shell disabled; bounded TERM grace is followed by KILL of surviving descendants, including when their leader exits first. Fault marker, child death and failed runtime health cause nonzero supervisor exit and container restart. Cancellation alone is not called CPU termination. The contextual Bandit B404/B603 suppressions match fixed trusted commands; B104 matches the keyed unpublished private-bridge gateway, with native llama still loopback-only. Core startup has no model-health dependency.
- `deploy/ai.compose.yaml` isolates models on ai_private, both AI/core bridges are internal, no AI host ports, no model DB credentials or DB bridge, proxy variables empty, loopback DNS, non-root/read-only/capability-drop/no-new-privileges/PID/RAM/CPU controls and component-only read-only weights/key mounts. Quoted tmpfs fixes the prior YAML comma interpretation. These protective limits are not CPU reservations: model limits 2+.75 and both AI workers .5+.5 can total 3.75 CPUs of the observed four-CPU host. Actual concurrent core/AI NFR still must be measured.
- `ai/native-artifact.lock.json`, `scripts/prepare-ai-native-cache.sh` and the optional `llm-prebuilt` Dockerfile target require exact equality to all 29 locked native/license/provenance files, reject extras/symlinks/different bytes, retain pinned source revision and original source-image provenance. Export does not run copied binaries. Default target remains pinned source compilation. This is a reviewed local cache of a genuine prior source build, not a signed distribution or generic arbitrary-binary acceptance. No model weights enter context/image/Git.
- `scripts/serve-ai-local.py` binds only 127.0.0.1, permits fixed project frontend service and optional explicitly selected local DB/Redis forwarding, validates internal bridge/private target, keeps TLS end-to-end and never exposes a model endpoint or accepts a caller-selected target. Concurrency, connection/read/write/idle waits are bounded. It is documented development ingress and must be restarted after container IP changes; it is not production ingress/installer acceptance.
- `llm_input` v5 preserves typed normalized current values, roles, units, quality/presence, status/reason/action, independent-group count and actual supporting/contradicting Decision summaries with allowed citation IDs. It removes unrelated case/source/value/fingerprint identifiers and repeated evidence lists. Model identity now pins v5 prompt/hash. Canonical full Facts remain backend-validated before/after inference; output grammar and separate validation still permit only three grounded clause codes/allowlisted citations. No five-group, unanimity, contradiction, human-commit, production flag, model/revision/quantization/context or token/deadline boundary was weakened. Logs add only bounded token counts, not prompts/IDs/output text.

## Evidence inspected and limits

Root v4 real Registry attempt remains FAILED at 118.1443 seconds; its JSON was preserved as `stage9-v4-real-llm-timeout-failed.json`. Actual supervisor restart evidence must remain linked to that failed attempt; it is not relabelled successful inference. Disk-full native build and interrupted integration are infrastructure failures, not PASS.

Root v5 real vertical: 2 PASS in 125.22 seconds, five genuine imported/confirmed Decision rows, five actual Qwen vectors, READY retrieval, deterministic demo recommendation, actual LLM COMPLETED, citation subset check, no AI business writes followed by explicit human confirmation. Root report backfill 13.5742 seconds, LLM job 93.1682 seconds; this is legally synthetic development evidence, not independent human semantic gold or a latency percentile.

`fk-stage9-isolated-network-v5-report.json` has actual model-info v5 / pinned embedding and LLM images and reports both model containers passing unauthenticated denial, public TCP denial, completed DNS denial, direct DB denial, no proxy/DB credentials, offline flags and inspected read-only/private policy. Scope is those two model containers. The helper itself iterates only embedding/llm (`scripts/check-ai-isolation.py:96`). The reviewer separately closed that evidence gap for the currently running profile: actual backend and both dual-network AI workers each denied external TCP, completed external DNS with denial, had no configured proxies and belonged exactly to the two internal bridges. This is actual negative connectivity evidence for those current containers, not a universal claim about other deployments. Direct external-IP TCP denial is measured; no arbitrary HTTP payload or enterprise data is sent.

Independent execution completed:

- **2 actual Qwen cases PASS in 89.55 seconds**, dedicated `fk-stage9-real-acceptance-v5` container exited0; `fk-stage9-independent-real-v5-repeat.log`. Reused root-authored acceptance tests with their actual providers/output unchanged, new own fixture schemas/queue namespaces, no mocks or model restart. This is independent execution of existing acceptance cases, not independently curated semantic labels. Independent vertical JSON `fk-stage9-independent-real-v5-vertical.json`: backfill13.558 seconds, LLM59.2815 seconds, five actual Registry precedents/vectors, COMPLETED with valid actual Decision citation, zero AI business writes and explicit subsequent human commit. Original root v5 JSON preserved separately as `fk-stage9-independent-root-v5-before-repeat.json`.
- **36 pure/owned-process/previous negative cases PASS in 6.41 seconds**, `fk-stage9-independent-v5-pure-supervisor.log`: current31 pure contracts including prompt projection, two actual owned subprocess termination cases, two independently written artifact/native-identity negatives and the independent canceled-thread admission regression. Process tests terminate only their own children; no model/service restart.
- Independently recalculated SHA256 for all **29 staged native files**, exact file-set and byte equality to `ai/native-artifact.lock.json`, pinned source marker match, no symlinks; PASS. No copied binary executed for this check.
- Actual model no-egress repeat PASS, `fk-stage9-independent-v5-model-isolation.json` / `.log`; actual backend+embedding-worker+LLM-worker denial PASS in `fk-stage9-independent-v5-worker-isolation.json`. Probe sends no prompt, credential, vector or enterprise data; one external-IP TCP connection attempt and completed public-DNS denial per process. No outbound HTTP application request was sent after TCP denial. This is a measured current-profile security boundary, not signed/offline customer distribution acceptance.

Repeated executions are not additional distinct coverage. Single successful LLM elapsed times are not p95/performance acceptance; earlier v4 timeout and infrastructure failures remain failed. Full integration was still running with its visible infrastructure failure at report time; no suite PASS inferred.

## Acceptance still open

Human-approved independent semantic gold/targets and production policy/activation remain BLOCKED. Real 10k representative-vector and ten-session core/AI performance, hardware sizing/cold-warm/recovery/backfill/rollback, full current integration/browser/security/UI gates, final source freeze and exact-final-HEAD green CI remain required. Root current integration log visibly contained an infrastructure test failure and has not completed. Root identified a hardcoded forest-keeper queue against this deployment’s configured Stage9 queue and changed the smoke to Queue(settings.import_queue_name); targeted/full rerun must finish before any PASS. The earlier disk-exhausted run remains FAILED, including its reported 231 infrastructure errors. This report supplies no READY TO MERGE or production approval.


## Checkpoint disposition

Reviewed UI404 recovery and outer Job.meta type guard are now present; prior completed-result freshness, cross-language idempotency, canceled-thread admission, artifact extra-file and native-identity findings remain fixed in source. Real auth/revocation/head/model/race integration evidence from root is separate from this reviewer execution. No new blocker in this review scope. **Continue Stage9 verification; not READY TO MERGE.** Independent actual inference and current no-egress checks now have direct reviewer evidence, while gold/performance/full-suite/final-source/CI boundaries above remain open.


## Reproducible independent backend/worker probe

The actual executed standalone reviewer script is `fk-stage9-independent-worker-egress.py` (temporary review artifact, no source edits). It prints no environments/keys/credentials or request data, executes no inference and mutates no containers or databases. It rechecks both actual network Internal flags, fixed three service memberships and image IDs, clears no runtime settings, sends one bounded public-IP TCP probe and performs completed-DNS-denial checks inside each process. DNS that remains pending fails; TCP/DNS success fails. Inspect/exec error aborts with nonzero status rather than claiming denial. Repeat command:

```sh
python3 /tmp/fk-stage9-independent-worker-egress.py \
  --project fk-stage9 \
  --output /tmp/fk-stage9-independent-v5-worker-isolation-reproducible.json
```

This exact reproducible script was executed separately and returned **PASS**. Its report adds actual image IDs and both internal-network flags to the initial independent probe. The existing model helper is separately repeatable:

```sh
python3 scripts/check-ai-isolation.py --project fk-stage9 \
  --output /tmp/fk-stage9-independent-v5-model-isolation.json
```

Do not reuse the development probe report as evidence for an untested customer network/deployment. Script SHA256: `bba1c0217865366813df6945b065d3024127c5b2e48e57855340b3c64bc306b0`.
