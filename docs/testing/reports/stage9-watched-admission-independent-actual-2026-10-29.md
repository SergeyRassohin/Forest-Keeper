# Stage9: independent actual-model retest after watched-admission correction

29 October 2026, Europe/Moscow. **Stage9 BLOCKED; not READY TO MERGE.**
[Safe results, complete app-source inventory and runtime provenance](stage9-watched-admission-independent-actual-2026-10-29.json).

## Independently executed current-source gate

Tested full business-source SHA: `9971e94d1efee899b06d0342ef4838f7b759b7f4`.
Fresh owned fixture `independent-final-watched-admission-v4`, committed bounded runner,
no concurrent parent model/CPU-heavy tests. **3passed,0skipped in107.72s; exit0, no OOM.**
All86application Python hashes matched9971e94before and after the run. The selected
actual-test files were unchanged; two other integration tests had inspected failure-only
diagnostic wrappers in the worktree. Their hashes are recorded, and those wrappers did
not execute in these three tests or change runtime implementations.

Executed exactly the genuine Registry→Qwen→grounded explanation→fixture human confirmation
vertical, actual scoped query preparation/retrieval, and actual shadow-checkpoint/new-worker
resume/cutover/rollback tests from `test_ai_real_integration.py` and `test_qwen_integration.py`.
The real-Qwen segments call the original pinned local providers, with no model-output
mock. Settings routing isolates disposable own schemas and queues. The legacy synthetic
vector space in the rollback test remains separate from the actual Qwen version.

The main vertical persisted5actual1024-dimensional vectors, returned5genuine Registry
precedents, completed its LLM explanation with validated citations, preserved business
digests during inference and initiated zero AI business writes. A separate explicit
fixture-human submission confirmed the final Decision. Measured backfill13.8091s,
LLM job65.1564s, vertical86.1668s. This run provides **one LLM-job timing, not a percentile**
or semantic-quality estimate. Full observed LLM identity, prompt/schema hashes and unchanged
embedding/LLM image identities are in the JSON.

Cold query preparation was also exercised: the initial GET enqueued bounded background
work, an actual Qwen query vector was prepared, and later GET retrieval succeeded without
inference in GET. A cold similarity GET shares the corrected admission helper; the entire
GET call graph is therefore not claimed unchanged. Warm-cached ranking/recommendation
SQL, validation and other85app files remain unchanged. Shadow recovery uses a fresh RQ
worker after a durable checkpoint, not a native-job SIGKILL or model-service restart.

## Independent security and evidence scope

Actual client checks confirmed non-root, read-only,1CPU/1GiB/PID128, cap-drop/no-new-privileges,
two owned internal networks, empty outbound proxies and selected mounts without Docker
socket, model weights or a whole-repository/secret-directory mount. Both models were
healthy after the run and had not restarted. No packet-level egress, browser or negative
cross-domain/IDOR probe was repeated here; their separately scoped evidence is preserved.

Raw logs and credentials remain private. Only this owned exited-zero client was removed
after complete state/log capture to recover space; all binds, source, weights and business
volumes were preserved. The reviewer made no business-source changes.

The [independent Redis/health review](stage9-watched-admission-health-independent-2026-10-29.md)
records11separate PASSs. The two new failure-only CI diagnostic wrappers were also inspected:
they call the real recovery/Budget implementations and re-raise errors, recording only
exception class, driver SQLSTATE, source basename/function/line and deadline overdue time.
No exception text, SQL, payload, locals, new retry, weaker assertion or extended budget
was introduced. No blocking source finding remains in this reviewed delta.

Reviewed latest parent actual/local-gate/source-provenance/CI-failure reports and current
scope wording. Their JSON includes no credentials, raw prompt or vector arrays. Source
provenance correctly distinguishes unchanged warm-cached ranking logic from the affected
cold-query enqueue path. The original43fcf12performance API/image and all historical raw
measurements remain bound to that earlier source; this run does not constitute new9971e94
performance measurement or reassign historical PASSs.

## CI and acceptance limits

Source9971e94push CI40892717583 succeeded, while PR CI40892726833 failed two other tests:
normalization concurrent starts returned `QUEUE_UNAVAILABLE`, and the profile-snapshot
integration exceeded the protective total1.5s Budget. Their causes are unobserved; neither
is labelled flaky or waived by local570integration/15browser PASS. The PostgreSQL timeout
lines in that CI log concern intentional negative-test `SELECT pg_sleep` statements and
do not prove the cause of these unexpected failures. The next exact-final-HEAD push/PR CI
must be assessed separately; no final-green claim is made here.

The independent current-source actual-model gate is **PASS**. Overall Stage9 remains
**BLOCKED**: historical loaded recommendation NFR fails, human-approved independent Gold
and targets are absent, supported production AI hardware/positive policy and signed
distribution#32 remain unaccepted, and final exact-HEAD CI is pending. Production AI and
positive production policy stay disabled. No merge, automatic issue closure or next-stage
implementation is authorized. #17/#18/#20 retain their separate DoD.
