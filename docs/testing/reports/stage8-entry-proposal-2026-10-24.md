# Stage 8 entry gate / proposal delivery

Date: 24 October 2026, Europe/Moscow. Scope: [issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29) §6.7 / §13.
Branch: `codex/stage8-recommendations`. **Proposal only; not implementation acceptance or READY TO MERGE.**

## Accepted base

The starting worktree was clean on the completed Stage 7 branch, HEAD
`055c8acbc7d2100cc04247b8980d422a7a9d8699`. No reset, history rewrite or deletion occurred.
GitHub confirmed PR #28 MERGED by the owner at `c927af513d29d83bd53b1b6522efccb42b5a1341`.
The [exact merge-commit workflow](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40079346518)
completed SUCCESS. Issue #27 is CLOSED. The separate Stage 8 branch starts from that main merge.

The entry comparison preserves the Stage 7 acceptance boundary: actual scoped immutable
Decision retrieval, explicit synthetic-only provider, no accepted production embeddings
or semantic quality. Similarity is not a recommendation or permission to create a Decision.
Existing 39 permissions remain canonical; `recommendation.view` and
`recommendation.accept_as_decision` already exist in XLSX and need no invented permission.

## Delivered before business implementation

[Architecture and numerical policy proposal](../../development/stage8-recommendation-proposal.md)
and the separate **Proposed decisions — not accepted** section in
[Decision Log](../../decisions/decision-log.md) record the precise choices, golden fixtures,
API/schema/file plan and all 14 carry-over dispositions. Runtime code, SQL schema,
dependencies, model manifest and historical Stage 7 reports remain unchanged.
Current README/progress/readiness/workflow documentation now records the accepted Stage 7
and the actual 6 / 7 / 8 / next 9 numbering without rewriting historical roadmap sections.

Proposed policy: demo only, at least 5 independent provenance groups, 100% agreement,
zero contradictions, complete above-threshold pool <=20 and explicit source correspondence.
Confidence is an absolute group count, never a probability. One prior case provides context;
production remains unavailable. None of these new numerical choices has owner approval yet.

[Independent architecture proposal review](stage8-proposal-independent-2026-10-24.md) corrected correlation by any shared input-file hash,
transitive current-case correlation, OPEN→IN_REVIEW token refresh, receipt idempotency order,
bounded scoped audit provenance and a proposed concurrency/activation protocol. This review
only assesses whether the proposal can be submitted to the owner; it does not approve policy
numbers, certify unimplemented locking or replace final implementation verification.

## Verification and remaining gates

- Local Markdown target checker: PASS, zero missing targets. No external HTTP-link sweep claimed.
- Existing gallery verifier: PASS, 27 retained screenshots / 135 retained responsive records,
  source tree matches. This is artifact validation, not new screenshot/browser execution.
- `git diff --check`: PASS.
- Gitleaks pinned scanner: Git history and tracked-content scans PASS, no leaks.
- Source scope inspection: Markdown-only changes; no application, schema, dependency or
  historical report edits.

Full Stage 8 unit/integration/browser/security/performance/production/restart gates:
**NOT RUN — implementation awaits policy approval**. Historical Stage 7 passing counts
are not reported as Stage 8 validation. Push/PR CI status for this documentation proposal
is tracked in its draft PR; it cannot establish that the absent engine passes acceptance.

Next required owner decision is approval/amendment of the concrete proposal at the PR's
reviewed commit. Issue #29 §6.7 expressly requires numerical policy approval before
implementation. Once approved, record the exact version/content/reference in Decision Log,
implement in this separate branch/PR, complete all §11 gates and independent targeted tests,
verify green push/PR CI at exact final HEAD, then stop at READY TO MERGE.
No merge, Stage 9 implementation or closure of #17/#18/#20 is authorized here.

Reviewed proposal SHA-256: `9d4dd635a4366ea762c1f92a5e37f2271cbf0b4bdfdf9274a6c2f5b67b712585`. Owner approval remains pending; a positive review of a proposal does not supply it.
