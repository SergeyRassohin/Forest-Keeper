# Stage 9 local development runtime

This is an opt-in **development/demo** CPU profile, not accepted production AI sizing or
semantic quality. Production AI and positive production recommendations stay disabled.
Running the models does not approve the proposed gold labels, thresholds or policy.
See [the preimplementation decision matrix](../development/stage9-local-ai-proposal.md)
and [the exact download/verification procedure](model-downloads.md).

## Preparation on a connected build machine

1. Prepare the ordinary development TLS/environment as in the repository Quick Start.
2. Download and byte-verify all14locked artifacts with `scripts/models.py`. Weights stay
   outside Git/images. The runtime mounts only its own component directory read-only.
3. Export the pinned native source with `bash scripts/prepare-ai-native.sh`. An already
   present local upstream Git repository may be selected by `FK_LLAMA_SOURCE_REPOSITORY`.
   The script exports only commit620d2225cc436ab0b001e3200e590e3b286ef9ab and a source hash
   inventory to ignored `work/stage9-native-src`. It refuses to overwrite existing staging.
4. Build backend/frontend normally, then build `embedding` and `llm` targets in
   `ai/Dockerfile`. The managed-cloud helper is `scripts/build-ai-with-proxy.sh` with
   `FK_ENV_FILE` pointing at the private environment file. It preserves proxy/TLS trust
   and mounts the CA only during networked build steps. The native compiler builds from
   staged source; compiler/source revision, source/binary hashes and license notices are
   retained in `/app/native`. The LLM image has no Torch/transformers dependency.
5. Preload both model images and ordinary core images on the target machine. No package
   install, model download or image pull is allowed during offline startup/inference.

Required private environment selectors, alongside normal core settings:

```dotenv
FK_AI_MODEL_ROOT=/absolute/path/to/verified/model-root
FK_AI_KEY_FILE=/absolute/path/to/private/ai-key
FK_AI_FILES_GID=1000
FK_AI_BACKEND_IMAGE=forest-keeper-backend
```

Create a random32byte-or-longer ASCII capability file without printing it; do not reuse a
user password or commit it. `FK_AI_FILES_GID` is the explicitly permitted local reader
group. The fixed non-root model/backend/AI-worker user receives that supplementary group.
Only the public locked artifacts and this capability file need group read access
(directories0750, files0640); do not change customer-data directory permissions. The key
is mounted as a file, never a command argument. Weights, capability and environment files
must not enter a Docker build context. Root `.dockerignore` uses a strict allowlist.

The single explicit source-role declaration in `FK_RECOMMENDATION_SOURCE_MAP` is operator
configuration. Missing/invalid/unknown roles cause abstention. Do not infer source authority
from A/B order or generate a production approval. All API replicas must use uniform
configuration. Quiesce/drain API/business workers before any active version/config switch;
a separate derived shadow worker may construct a new index without changing the old API.

## Offline startup

```sh
docker compose --env-file /private/path/dev.env -f compose.yaml \
  -f deploy/ai.compose.yaml --profile ai up -d --no-build --pull never
```

The additive file is intentionally explicit: ordinary core Compose does not start AI.
Core startup/health/manual review never depend on model readiness. Models publish no
ports. Only the private bridge carries model RPC; models have no DB credentials, import
mounts or membership in the DB bridge. Both bridges are `internal`, including the core
bridge used by dual-network AI workers. External DNS uses loopback; proxy variables are
cleared only inside these deliberately offline application containers. This is application
isolation, not a workaround for the managed build network policy. Actual DNS/HTTP denial
and reachability must be measured, not inferred from these settings alone.

The model containers are non-root, read-only, capability-free, with no-new-privileges,
private bounded `/tmp`, PID limits and component-only artifact mounts. Fixed local RPC
requires the file capability; HTTP redirects/public hosts/arbitrary paths are rejected.
Native llama listens only on loopback in its own LLM container. No end-user bearer API
is introduced. The public browser continues to use the existing HttpOnly session cookie.

CPU development budgets are LLM2CPU/16GiB, embedding0.75CPU/6GiB, each AI worker0.5CPU/
512MiB. These are protective limits, not reserved CPU cores or a supported NFR claim.
Native context stays32768; each input totals at most4096tokens, output256tokens. Embedding
batches contain at most8items. AI queue admission is atomic, maximum8pending+active and
one request per actor; backfill leaves two user slots. SQL snapshots end before inference.
Global/actor leases expire after450seconds; queue wait TTL240/job180/result900seconds.

At118seconds the gateway closes admission and writes a private fault marker. The PID1
supervisor polls that marker and child/health status, terminates only process groups it
created, then SIGKILLs surviving computation after at most5seconds of grace. Docker
restarts the failed container with a fresh ephemeral filesystem. Canceled gateway tasks
also close admission; Python thread cancellation alone is not claimed as CPU termination.
User cancellation is logical discard: a running bounded inference may finish, and its
result cannot be delivered. Worker/model downtime leaves the manual path available.

## Evidence and remaining gates

Two owned-process tests exercise SIGTERM-resistant computation and surviving descendants,
and a gateway-fault marker causing nonzero supervisor exit/process death. Pure cancellation
and private admission tests cover the gateway side. API tests use actual DB/Redis/RQ/auth
and an explicitly stubbed model; they are not real-model acceptance. Separate opt-in
`test_qwen_integration.py` uses actual embeddings and asserts no held SQL connection or
version advisory lock while inference runs.

Initial host real-model results, including two failed LLM attempts, remain in
[the historical report](../testing/reports/stage9-initial-real-models-2026-10-26.json).
Container/offline/vertical/restart/NFR evidence must be reported separately for the current
source/image. No GPU,100kcapacity, signed release or human-gold quality claim follows from
this profile. Signed supplier distribution remains a bounded downstream dependency#32;
checksums/source pins are not signatures. Full Stage9 acceptance and independent real
inference review remain required. No merge or next-stage acceptance is implied.

### Local incremental native cache and development ingress

The32GiB workspace disk filled while repeating the native source build alongside live
services. The failed build and interrupted integration run remain failed infrastructure
evidence; no business volumes were deleted. For incremental Python/prompt development,
`bash scripts/prepare-ai-native-cache.sh` can export `/app/native` from an already built
local LLM image without running it. All29native/license/provenance files must match
`ai/native-artifact.lock.json`; extras/symlinks/different bytes are rejected. Staging stays
outside Git. `FK_AI_LLM_BUILD_TARGET=llm-prebuilt` selects this optional build target.
Default `llm` still builds from the pinned source. This local byte lock is not a signed
supplier distribution. The original source-built image ID is historical provenance;
future compiled bytes/toolchain changes require a reviewed new lock/evidence.

Docker's internal-only bridge does not publish the declared host port mappings. For the
local development browser, keep a fixed host-side loopback ingress process running:

```sh
python3 scripts/serve-ai-local.py --project forest-keeper --https-port 8443
```

This bounded relay targets only that project's frontend inside its internal bridge and
preserves TLS end-to-end; it never exposes model RPC. Restart it after recreating frontend
containers because private addresses may change. Optional `--database-ports` plus explicit
`--postgres-port`/`--redis-port` provide loopback-only operator/test access. They are off by
default. Customer production ingress/firewall/installer setup and acceptance remain a
separate requirement; this helper is not an Internet proxy or a production installer.

Run `python3 scripts/check-ai-isolation.py --project forest-keeper --output /tmp/ai-isolation.json`
to check actual model metadata, credential-free model environments, denied unauthenticated
RPC, denied public TCP/DNS and direct DB connections, and private read-only container policy.
The report has no prompt/vector/key. A DNS timeout that has not completed is not counted
as proof of denial. The test is an explicit separate actual-runtime gate, not a CI mock.

For the dual-network consumers, also run `scripts/check-ai-workers-isolation.py` with the
same `--project`/`--output` arguments. It probes backend and both AI workers, requires
exact membership in both internal bridges and denied external TCP/DNS/empty proxies.
It reads only selected Docker metadata; it does not dump service credential environments.

The local operator/test ingress has a bounded128connection limit/backlog. Redis WATCH
admission can hold two connections per request; the20request race test needs40, so the
initial32connection helper limit incorrectly cut transport connections before Redis.
This changes only the development relay, not AI queue capacity8/actor1 or request deadlines.
`--database-only --database-ports` can start separate loopback DB test ports without an
HTTPS listener; it lets an operator change test ingress without interrupting active sessions.


The separate [resumable actual-vector capacity run](../testing/stage9-capacity-run.md)
uses an explicitly owned development fixture and records calibration/full-run results
separately. Its warm ASGI baseline does not replace the remaining AI/core, HTTPS,
cold/warm, semantic-quality or supported-hardware gates.

Final development measurements on29October are summarized in the
[current acceptance checkpoint](../testing/reports/stage9-development-acceptance-2026-10-29.md).
The real10kindex is complete. Idle ten-session HTTPS passes, but loaded recommendation
p95=1.044695s during startup and1.102804s during generation exceeds the mandatory1s
baseline. The4CPU/32GiB host is a limited development demonstration, not an accepted
production AI hardware profile. No8CPU/100k/GPU sizing guarantee follows from it.
Human Gold/targets, production policy, signed packaging#32 and final exact-SHA CI
remain separate gates; Stage9 is BLOCKED and production activation stays disabled.
