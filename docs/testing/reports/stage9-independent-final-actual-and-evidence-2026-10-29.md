# Stage 9: independent final actual-model and evidence review

29 October 2026, Europe/Moscow. **Stage9 BLOCKED; not READY TO MERGE.**
Independent verification required by AGENTS.md; no merge or next-stage acceptance.
[Machine-readable evidence and complete source inventory](stage9-independent-final-actual-and-evidence-2026-10-29.json).

## Independently executed actual inference

Tested full SHA: `43fcf12b334a5d457bfafbf3afe56be801d33c4b`.
Application Python bytes are unchanged from
`d47fa17b74f23360fb9b803b138f1efeec9dc566`; all86Python file hashes matched before
and after this run. Later report-only commits require their own exact-final-HEAD CI.

Fresh owned fixture `independent-final-profiles-v3` ran the committed runner's
`verify` mode independently, without concurrent parent inference. **3passed,
0skipped,117.48s; container exit0, no OOM.** The two selected files contain exactly:

- `test_real_imports_precedents_qwen_retrieval_and_grounded_llm_leave_decision_to_human`;
- `test_real_qwen_backfill_query_and_scoped_lookup_preserve_manual_history`;
- `test_real_qwen_shadow_checkpoint_new_worker_cutover_and_test_space_rollback`.

The first test produced5actual persisted1024-dimensional Qwen vectors, genuine Registry
precedents and a completed grounded LLM explanation. Citations were validated, business
digests remained unchanged during inference, AI initiated zero business writes, and a
separate explicit fixture-human submission saved the final Decision. Backfill15.306s,
LLM job71.1286s, vertical93.4324s. This single job is **not a percentile**.

Actual LLM identity: `Qwen/Qwen3-8B-GGUF`, revision
`7c41481f57cb95916b40956ab2f0b139b296d974`, artifact SHA256
`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`,
Q4_K_M/context32768, grounded-clauses-v5-minimal-comparison. Actual embedding tests
use the unchanged pinned `Qwen/Qwen3-Embedding-0.6B`/1024 baseline, revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, artifact SHA256
`0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
No model/output replacement was used. Settings injection selected disposable owned
schemas and queues; the embedding observation wrapper calls original real inference
while checking released SQL connections/advisory locks.

Other assertions covered background query preparation, no inference from GET, separate
core/AI queues, shadow partial-activation refusal, a fresh RQ worker resuming a durable
checkpoint, full cutover, separate vector spaces and rollback preserving history.
This is checkpoint/new-worker recovery, not a mid-native-inference SIGKILL experiment.
The actual scoped lookup does not replace separate negative cross-domain/IDOR tests.
All fixtures are legally synthetic; their explicit test confirmations are not human Gold.

## Runtime and privacy boundary

The independent client was non-root, read-only,1CPU/1GiB/PID128, with dropped
capabilities and no-new-privileges. Its exact two Compose-owned bridges were internal;
outbound proxies were empty. Selected mounts contained no Docker socket, model weights
or whole-repository/secret-directory mount. Source and model-image hashes, bounds,
selected mount destinations and observed model metadata are recorded in the JSON.
Both models remained healthy and were not restarted during this run.

The reviewer inspected network configuration; this run did not repeat packet-level
egress or adversarial/IDOR negative probes. The separately recorded final isolation
probe remains its own evidence. Raw pytest logs, credentials and fixture tokens stay
in the ignored private directory. Only the known owned exited-zero client container
was removed after log/state capture to recover disk space; all bind evidence, source,
model files and business volumes were preserved. No business source was edited.

## Independent final evidence checks

Reviewed the current acceptance checkpoint, capacity runbook, owner-review document,
README, runtime guide, progress update and preserved proposal/decision-matrix update
against the available issue31 specification and repository invariants. No new blocking
architecture/security/product-intent source finding remains in this scoped review.
The two performance corrections retain canonical hashes and per-evaluation profile
freshness, without new policies, global caches, SQL changes or weaker deadlines/access.

Independently recomputed every endpoint p95 from400ASGI and three500-request HTTPS
reports:100observations per endpoint, every response valid HTTP200 with no error.
Recorded PASS/FAILED flags match the unchanged per-endpoint1second NFR:

| Final workload | Recommendation p95 | Result |
|---|---:|---|
| Warm ASGI |0.868401s|PASS|
| Actual HTTPS, models idle |0.801118s|PASS|
| Actual HTTPS, LLM startup/ready transition |1.044695s|**FAILED**|
| Actual HTTPS, successful LLM generation |1.102804s|**FAILED**|

Ten canonical business-table digests match from the original partial-backfill report
through all three final HTTPS observations. The original10000-vector index is retained.
All94deployed Python/JSON file hashes match the checkout. Referenced exact observer
sources exist and match their SHA256; the six local-gate private-log hashes also match.
Those six gates were executed by the parent; this reviewer verified evidence rather
than claiming a new independent full integration/security-suite execution.

The entire generation HTTP window is inside a successful actual LLM phase with substantial
LLM CPU activity. Startup HTTP extends1.153438s beyond the first retained healthy check,
so it is correctly described as a startup/ready transition, not wholly pre-ready traffic.
The seven correlated-small-pool, two below-threshold and one oversized-pool query results
are not independent positive semantic-quality evidence. Public JSON/source artifacts
reviewed here contain no credentials, raw prompts or vectors.

## Acceptance disposition

The independent actual-model gate is **PASS**. Stage9 remains **BLOCKED** because:

- Loaded recommendation latency fails the mandatory NFR on the measured4CPU/32GiB
  development host. Idle success and successful LLM jobs do not waive those failures.
- Human-approved independent materialized Gold, sealed separation and preapproved
  semantic targets are absent;200candidate outlines remain unlabelled proposals.
- A supported production AI hardware profile and positive production policy are not
  accepted. No8CPU,100k/GPU or industrial-capacity guarantee follows.
- Signed offline distribution remains the bounded unresolved dependency#32; SHA checks
  are not supplier signatures.
- Exact-final-HEAD push/PR CI remains pending. The initial configured GitHub authentication
  failure was temporary: normal access recovered and report checkpoint
  `5b17f2900211cb8f3939278e2c3fe82ade7a84e7` was pushed to the open draft PR33.
  Its push40891443450/PR40891444945 runs were queued when reported. Neither those
  queued runs nor earlier green CI establish success for the subsequent final report
  follow-up commit. The original access failure remains historical evidence.

Production AI/positive production recommendations stay disabled. No merge, issue closure
or next-stage implementation is authorized. #17/#18/#20 retain their separate DoD.
