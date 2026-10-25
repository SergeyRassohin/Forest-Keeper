# Stage 9 — architecture and acceptance proposal

26 October 2026. [Issue #31](https://github.com/SergeyRassohin/Forest-Keeper/issues/31).
Branch `codex/stage9-local-ai`, based on accepted main
`54d3939d704bfe6aa1c943bef3e70b83b01c0527` / PR #30;
[exact main CI SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40198679543).

This proposal is published before implementation. Starting Stage 9 authorizes development,
not new numerical product policy, production semantic activation or merge. Stage 0–8 are
accepted in main. Historical Stage 7/8 reports retain their actual dated limits.

## Inventory and scope

The repository contains the complete SHA-256/size lock for14 upstream files, the download/
verification tool,1024-dimensional derived vector tables, bounded RQ backfill/query jobs,
version activation/rollback, scoped retrieval, deterministic recommendations and Human Review.
No model weights were found in the selected workspace. No Qwen runtime exists yet. Current
production retrieval is unavailable; the test provider is explicitly synthetic. The current
five-group demo policy is not a production recommendation policy.

Baseline is unchanged:

- LLM `Qwen/Qwen3-8B-GGUF`, revision `7c41481f57cb95916b40956ab2f0b139b296d974`,
  `Qwen3-8B-Q4_K_M.gguf`, Q4_K_M, configured context32768, non-thinking, structured output;
  GGUF SHA-256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
- Embedding `Qwen/Qwen3-Embedding-0.6B`, revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`,
  sentence-transformers,1024 dimensions; weight SHA-256
  `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
- All tokenizer/config/pooling/license/card bytes must also match `models/artifacts.lock.json`.
  No weights, caches, prompts with customer data or generated model bundles enter Git/CI artifacts.

## Architecture and exact planned changes

`backend/app/ai/` contains model-agnostic contracts, bounded local transport, versioned input/
prompt/output schemas, input minimization, reference/fact validation and explanation execution.
Heavy ML dependencies live in a separate `ai/` runtime package with its own pinned lock;
backend installs no torch, transformers or llama model weights. Runtime candidate pins:
llama.cpp release v0.7.0 commit `620d2225cc436ab0b001e3200e590e3b286ef9ab`,
sentence-transformers6.2.0/transformers5.20.2/torch2.14.1 CPU, subject to resolver/security/runtime
verification before support claims. Any replacement is recorded, not silently floated.

EmbeddingProvider and LLMProvider remain separate. Local embedding service loads the complete
verified snapshot with `local_files_only=True`, `trust_remote_code=False`, safetensors and
last-token pooling. Inputs are bounded, versioned canonical JSON without chosen outcome,
actor names, reasons, credentials or full raw records. Retrieval instruction/preprocessing,
artifact lock digest and runtime versions are part of the provider/version identity.

Existing `backend/app/similarity/{provider,service,jobs,cli}.py` gains explicit Qwen-demo
configuration and provider-version validation; test configurations and IDs remain unchanged.
Only bounded background jobs perform inference. No vector calculation in public GET.
Synthetic vectors cannot be labelled Qwen and equal dimensions never imply compatible spaces.
Existing DB vector/version/checkpoint tables suffice initially; no business schema migration
is proposed. A migration requires an explicit additive design if this assessment changes.

Qwen real-model development mode is labelled `LOCAL_QWEN_DEMO`, distinct from synthetic
hash vectors and from accepted production semantics. Production retrieval remains blocked
until a versioned, independently checked semantic acceptance record exists. Existing
`stage8-demo-unanimous-v1` may operate only in explicit test/development mode; no production
positive recommendation is enabled. Its five independent groups/unanimity/correlation/source
mapping rules stay unchanged. Two cases can demonstrate real retrieval, not bypass the
five-group recommendation requirement; positive E2E uses five independent histories.

LLM consumes only backend-authorized facts and selected valid precedent references, never
DB credentials/SQL/tools/source network access. Structured output contains evidence IDs and
bounded factual clause codes, the exact deterministic status/action and context fingerprint.
Backend checks every reference against the supplied allowlist and every factual clause against
the deterministic evidence. Russian/English explanation is rendered from those validated
clauses; arbitrary generated prose and unsupported factual claims are rejected. This deliberately
limits generation to grounded explanation rather than pretending that a JSON schema can prove
arbitrary free text true. Actual Qwen generation remains mandatory for runtime acceptance.

Internal AI service owns `/internal/ai/{recommend,explain,health,model-info}`. `recommend`
only explains the supplied deterministic proposal; it cannot choose business truth. These
routes are absent from public backend and reverse proxy. Services use a private isolated
network, no published AI ports and a file-backed service capability checked in constant time;
this is not an end-user bearer API. The model runtime has no database/import-file mount.

Proposed public API addition, using existing cookie+Origin and `conflict.view` plus
`recommendation.view`, without new permissions:

- `POST /api/v1/conflicts/{id}/ai-explanation`: explicit bounded asynchronous request,202
  with opaque actor/session/case-bound handle. No business write or source modification.
- `GET /api/v1/conflicts/{id}/ai-explanations/{handle}`: bounded status/result, no inference.
  Unknown/foreign handles are opaque404. Responses have `Cache-Control: no-store`.
- Existing RecommendationResult/Decision lifecycle and optional recommendation receipt are
  unchanged. Explanation does not authorize form prefill/commit or enter Decision evidence
  as a new assertion of truth. Existing current review token and human confirmation remain.

RQ uses a separate bounded AI queue/worker to avoid blocking imports/manual workflows.
Job arguments contain IDs/digests, not raw prompts. Redis-derived results have bounded TTL,
size and actor/session binding; Redis unavailable means explanation unavailable, not failure
of manual Decision. Before input and before delivery, verify fresh auth/scope, current
Conflict/Decision heads, retrieval/model/prompt/policy/source-map digests. Stale or revoked
work is discarded. Snapshot transactions close before long inference; no SQL/gate lock is
held across model generation. In-flight local inference may finish after revocation, but its
result can never be delivered without fresh authorization. No cross-domain IDs/counts leak.

Frontend adds a separate labelled local-AI explanation panel to Human Review and real IDs
as links. Deterministic facts/recommendation remain separately visible. Pending/error/stale/
queue-full/invalid-output shows explicit unavailability and retains the draft/manual path,
light/dark, keyboard focus and mobile/desktop layout. No hidden LLM request on GET/page load.

## Hardware, operational resource budgets and offline supply

Observed candidate cloud host:5 schedulable CPU,about33GiB RAM, no nvidia-smi/GPU found;
about10GiB disk free before downloads. This is an inventory, not a supported AI profile.
Weights occupy about6.22GB plus tokenizer/config; Python dependencies, llama build, KV cache,
containers and temporary download space need additional capacity. Reclaim disposable build
cache where needed; never delete business volumes or previous stage work.

Initial protective development budgets, not quality thresholds or latency promises:
LLM one generation/3 CPU threads, embedding one batch/1 thread, input JSON<=32KiB,
embedding batch<=8 and bounded tokens, LLM generated<=256 tokens, total configured context
32768, provider deadline120s, job deadline180s, bounded pending queue8/actor one active job,
result TTL15min. Refuse overload explicitly. Tighten limits based on measurements; never
weaken core API NFR p95<=1s/10 sessions, Conflict card<=2s or health<=1s. Heavy work stays
asynchronous. A provisional32GiB CPU development profile is measured, not called supported
until actual cold/warm startup, load and memory results exist. GPU is unverified here.

Build/download may use the managed proxy with CA verification. Customer runtime has no
external egress, proxy credentials, telemetry or download-on-demand. Images/models installed
before startup; disable Hub/Transformers online behavior, telemetry and remote code. Internal
AI-only bridge has no external route, no DB peers and no published ports; external DNS and
HTTP denial are tested rather than inferred from environment flags. Read-only/non-root,
dropped capabilities, CPU/RAM/PID limits and exact health/model-info apply to AI services.

Local verification must check every locked byte before model load. Offline checksum bundle
includes manifests, compatibility/runtime locks, Apache-2.0/MIT and dependency notices/SBOM.
A checksum is not a signature. Supplier signing/installer integration depends on downstream
Update/offline supply work in #32; until actual signature verification is proven, signed
customer distribution remains BLOCKED. No supplier private key is invented or shipped.

## Threat model and test boundaries

Untrusted values/source names/comments/XML/model output cannot become instructions, HTML,
SQL, URLs, tool calls or new business actions. Allowlist input fields, cap bytes/tokens,
minimize PII and reject known credential/contact patterns. No claim of perfect PII detection:
customer data classification and legitimate processing authorization remain operator duties;
acceptance fixtures are lawfully synthetic non-personal data. Do not send human reasons or
full raw payloads. Never log prompts/vectors/raw/provider errors/credentials. Errors are
fixed sanitized codes; audit metadata stores only safe IDs/digests/version/timing/outcome.

Test wrong artifacts/revision/dimensions/NaN/zero vectors, malicious output and fake citations,
unsupported clauses, injection/XSS, SSRF/redirects/public addresses, oversized payloads,
timeout/cancel/overload, no-egress including DNS, backend/public AI route denial, IDOR,
revocation during work/poll, supersede/reopen, activation/cutover and idempotency. Verify core
FK without either model, with Redis/provider failures and after full restart. No fake output
can substitute for the separate real-model profile. Core CI remains lightweight; real-model
acceptance is explicit and reports exact artifacts, runtime/hardware/source provenance.

## Gold design and numerical proposal — NOT APPROVED

Product/domain owner must approve labels and targets before scored evaluation; no existing
human-labelled benchmark or accepted targets were found. Production activation stays BLOCKED.
Proposed legally synthetic benchmark:200 query cases,100 with1–5 relevant independent
precedents and100 hard negatives; multiple material/product families, Russian/English names,
near lexical matches with distinct identity, unit/domain incompatibility, incomplete/reopened/
contradictory cases. The runtime five-history demo is not this quality set.

Split by entity/source/provenance family (not random row):50 development cases for prompt/
preprocessing choices and150 sealed evaluation cases, with no shared file/key/semantic clones
across partitions. Human-approved labels/label version and dataset digest are frozen before
measurement. No training/model-weight changes. Independent reviewer checks split leakage,
label provenance and metric implementation. A generated fixture is only a candidate until a
human approves its labels; do not report AI-authored labels as human gold.

Proposed acceptance targets for owner consideration:

- precision@5>=0.95, calculated over returned compatible above-threshold results (at most5,
  without padding), micro-aggregated across queries; empty retrieval gives no false precision.
- recall@5>=0.90 over the positive set with1–5 labelled relevant precedents/query;
  abstention/missed positives count as misses. Report macro/micro and denominator counts.
- zero incompatible/cross-scope returned records, zero false-positive results for labelled
  no-match queries and zero harmful positive proposals on the adversarial safety set.
- LLM:100% delivered citations belong to supplied authorized evidence;100% delivered action/
  facts agree with deterministic policy,0 unsupported delivered clauses; report rejected/
  unavailable outputs separately, never count them as successful explanations.

These are proposed targets, not measured achievements. Existing0.85 similarity threshold
and five-group policy stay unchanged; Qwen compatibility is measured, not assumed. Any new
production threshold or positive recommendation policy needs separate explicit approval,
version/hash, compatibility evaluation and independent safety review. A failed metric stays
FAILED; target/label changes create a new version and a fresh held-out evaluation.

## Decision matrix and owner queue

| Topic | Disposition | Owner | Evidence / approval needed |
| --- | --- | --- | --- |
| Model identity/dimension/quantization | RESOLVED_STAGE9 design only | Implementer + independent reviewer | Existing approved manifest; full local hashes and real model-info still required |
| Architecture and minimized grounded output | RESOLVED_STAGE9 design only | Implementer + security reviewer | This preimplementation contract; adversarial/real inference still required |
| Semantic gold and targets | BLOCK_PRODUCTION | Product/domain owner + independent semantic reviewer | Approve proposed metrics and actual frozen human labels before scored evaluation |
| Qwen cutover/rollback/partial coverage | RESOLVED_STAGE9 design only | Implementer + data/security reviewer | Distinct version digests, dual-index, complete coverage, explicit switch/rollback tests |
| CPU/GPU sizing/performance | BLOCK_PRODUCTION | Performance/deployment owner | Actual host cold/warm/10 sessions/10k vectors/RSS/disk; GPU/100k remain unverified |
| Production positive policy | BLOCK_PRODUCTION | Product/domain owner | Existing demo policy unchanged; new approved version/calibration before activation |
| Source mapping/units/authority/Rules | DEFER_LINKED | Domain owner, Stage10/#17/#32 | Exact existing compatibility/map and NOT_CONFIGURED/NOT_DEFINED retained |
| Temporal/security/recovery | RESOLVED_STAGE9 design only | Implementer + independent security reviewer | Fresh auth/snapshot, stale discard, restart/reindex/revoke/error tests |
| External reviewer/private access | DEFER_LINKED | Repository/product owner, #18/#20 | Explicit invitation and own-file acceptance; Stage9 CI does not close them |
| Signed offline installer/supply | DEFER_LINKED | Supplier release/security owner, #32 | Real signing/verification pipeline; unsigned development checksums are not customer release |

Requested owner decisions: approve/revise the proposed quality targets and the future
human-label review arrangement; keep all production activation disabled meanwhile. No new
approval is needed to implement and test isolated local development adapters under the
existing baseline. This proposal does not claim those adapters already exist.

## Delivery gates

Unit/integration/browser/security/SAST/SCA/secrets/build/migration regressions; actual verified
Qwen embedding+llama.cpp inference, pgvector persistence and separate version migration;
no-egress offline/stop/failure/restart evidence; real hardware/performance and quality report
with any unapproved or failed gate explicitly BLOCKED; both-theme gallery/Axe/responsive;
independent real inference/security/product review; exact final push/PR CI. Stop READY TO
MERGE only when all required gates pass, otherwise report BLOCKED with actual evidence.
No merge, no auto-close of #17/#18/#20 and no next-stage implementation.
