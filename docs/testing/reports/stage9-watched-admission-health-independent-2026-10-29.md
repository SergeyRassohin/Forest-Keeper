# Stage9: independent watched-admission and health-test review

29 October 2026. Tested source `9971e94d1efee899b06d0342ef4838f7b759b7f4`.
[Safe machine-readable results, source hashes and private-log hashes](stage9-watched-admission-health-independent-2026-10-29.json).
**Stage9 BLOCKED; no merge or production acceptance.**

## Independent execution

**11passed in1.89s, exit0:** six health tests and five actual-Redis admission tests,
including both new deterministic interleavings. Explicit private configured
`core-check.env` selected the owned development services. Each Redis fixture used a
fresh UUID namespace; these queues execute no model jobs. No model calls, restart,
business-source edits or general data cleanup were performed by this review.

Only `app/ai/admission.py` differs from the earlier43fcf12actual-model checkpoint;
the other85Python app files, including runtime health and warm-cached ranking/recommendation
logic, are byte-unchanged. A cold similarity GET enqueues query preparation through the
fixed admission helper; the entire GET call graph is not claimed unchanged. JSON records the exact changed-file hashes and the complete
86file inventory digest, reconstructible from the tested Git commit. Historical
[43fcf12actual results](stage9-independent-final-actual-and-evidence-2026-10-29.md)
retain their original source and measurements. They are not fresh9971e94runtime or
performance evidence. The subsequent [independent actual-model retest](stage9-watched-admission-independent-actual-2026-10-29.md)
passed separately; it does not reassign historical measurements to the new source.

## Watched Redis refusal correction

The parent reproduced two pre-fix failures with real Redis: an idempotency winner
committed after the loser's missing-job read, making the loser report `AI_ACTOR_BUSY`
or `AI_QUEUE_FULL` before validating its dirty WATCH. The retained private log records
**2failed,3deselected in0.33s**; this reviewer verified its hash and did not erase or
relabel those failures.

The correction validates WATCH using empty MULTI/EXEC before either refusal. Redis-py
executes this transaction while watching even when it has no mutation commands.
An intervening winner causes WatchError and the existing bounded retry discovers its
job. The existing route then enforces immutable request-language binding and returns409
for a conflicting language. Stable genuine busy/full conditions still refuse admission.

Independent deterministic cases commit a real RU winner while an EN loser holds its
earlier watched read. The loser returns the existing-job result, the stored winner stays
RU, and queue/admission counts remain exactly1or8as appropriate. Existing concurrent
tests retain the global8/background6/per-actor1bounds and rollback checks. Retry count3,
lease450s, queue TTL240s, ownership and deadlines are unchanged. No additional slot or
lease is created by the empty validation transaction. No blocking source finding remains.

## Health instrument correction

Runtime health code did not change. The former test compared full TestClient wall time
against0.1s despite a configured0.02s dependency timeout; client/scheduler overhead was
part of that measurement. The revised test holds the dependency on an Event, requires
503/database-unavailable while the dependency remains unfinished, and observes two
**real** asyncio.wait_for calls with the unchanged0.02s timeout. Only the health module's
asyncio reference is wrapped; real gather/to_thread/wait_for execute normally.

Release occurs in finally inside the TestClient context. The5s Event wait is a failure
cleanup bound, not an enlarged health deadline. Together, causal ordering and actual
timeout-argument assertions test dependency cancellation without treating host scheduling
as application latency. This does not measure or waive the separate runtime health NFR;
the earlier CI failures remain historical failed observations.

## Remaining gates

Parent full integration and separate new-source parent/independent actual-model retests
have subsequently passed; exact-final-HEAD CI still requires its own result. No actual-model
or performance PASS is claimed by these11tests themselves. In particular, original43fcf12loaded recommendation NFR FAILs
remain FAILs; the deployed admission-file difference is explicit and no new-image
performance measurement is implied.

Human-approved Gold/targets, supported production AI hardware and positive policy,
signed distribution#32 and the other Stage9 acceptance conditions remain open.
Production AI/positive policy stay disabled; no merge, automatic closure of#17/#18/#20
or next-stage implementation is authorized.
