# Stage 8 — deterministic Recommendation Engine

Scope: [issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29), including §14 light/dark themes.
**In development in PR #30; not accepted in main or READY TO MERGE yet.**
Owner approved all eight product-policy points in this chat on 25 October 2026:
«Согласен со всеми пунктами.». [Decision Log](../decisions/decision-log.md) records approval,
the exact [historical architecture proposal](stage8-recommendation-proposal.md) commit/digest
and additive physical representation. Historical pending proposal records are not rewritten.

## Product boundary and policy

Similarity measures context closeness; Recommendation proposes a current action;
Decision is a separately confirmed immutable human fact. PostgreSQL structured history is
the memory. No Qwen/LLM, new embedding provider, external API, model training, source write-back,
RuleSuggestion, automatic Conflict resolution or Rule/Template/Forest Codex change is added.

`stage8-demo-unanimous-v1` is a versioned server policy: complete pool <=20 above-threshold
precedents, minimum5 independent groups, unit group weight, agreement100%, disagreement0,
dominance margin1. Existing Stage7 full-precision cosine>=0.85 only filters similarity;
its value is never evidence confidence. Confidence is the integer independent-group count
when recommended, with unit INDEPENDENT_PROVENANCE_GROUPS; otherwise null. UI shows groups,
never probability/percentage. Every numerical change requires a new explicit policy version.

Five cloned facts or repeated imports are not five independent cases. The full correlation
graph includes the current case before exclusions; any shared input file SHA-256, RawRecord,
scoped business key or semantic frozen evidence joins a connected component. The current
component gives no support. A contradiction inside a group or any other qualified precedent
vetoes the recommendation, including a5:1 majority. Conservative grouping can undercount
real-world independence; it is demonstration evidence, not production quality/calibration.

Only current effective SELECT_VALUE/ENTER_VALUE heads on RESOLVED historical cases pass
Stage7 eligibility. The current case is excluded, as are superseded/reopened/uncertain cases.
Historical ENTER_VALUE remains context and vetoes a ready action; values are not copied
without an accepted applicability/rule policy. A proposed SELECT_VALUE always identifies
one selectable value in the **current** frozen Conflict, never a historical value/source ID.
Current resolved/insufficient/reopened/deferred-head cases abstain; GET never starts review.

## Provider and source correspondence

Production is deliberately **UNAVAILABLE**, even if test-provider opt-in flags are set.
Stage7's synthetic provider proves infrastructure, not semantic quality. Positive results
require explicit test/development mode, Stage7 test-provider opt-ins, `FK_RECOMMENDATION_ENABLED=true`
and an explicit operator-owned `FK_RECOMMENDATION_SOURCE_MAP` JSON declaration. Missing or
ambiguous correspondence abstains; source names/A/B order/file extensions do not assign truth.

Source declaration fields: version, approved=true, approval_reference, exact domain/entity_type/
attribute_code, allowed matching_profile_hashes and sources[{source_id, source_type, role}].
Source types remain existing FILE/ONE_C; logical correspondence roles are not User roles,
new permissions or an authoritative-source rule. Each historical/current case must cover
two unique source identities/roles with validated frozen type, source/file/raw/value lineage,
normalization origins and matching context. Legacy unknown types and stale profiles fail closed.
Raw payloads are never loaded merely to validate recommendation provenance.

The declaration is private server release configuration, not a user POST/body override.
Declare actual source IDs explicitly. Changing a declaration/model/policy invalidates derived
results; all API/worker instances must quiesce/drain before immutable configuration replacement,
then restart with identical digests. Mixed-config hot/rolling activation is not supported by
this bounded iteration. Existing source authority_scope metadata is not an active authority policy.
Rules/Template/Codex remain NOT_CONFIGURED, authority NOT_DEFINED; no shadow rule is invented.

## API, scope and bounded work

`GET /api/v1/conflicts/{id}/recommendation`, HTTPS cookie session only.
Existing conflict.view + decision.view + recommendation.view and explicit domain grants apply;
39 permissions/XLSX are unchanged. ADMIN has no implicit business scope/authority. Inaccessible
and missing cases have the same404; restricted empty pools do not reveal foreign history/counts.
All client query overrides are422. Authentication, scope, eligibility, coverage, evidence and
ranking share a read-only REPEATABLE READ snapshot beginning before auth reads.

Result fields include status, optional current action/source/value refs and typed value,
confidence/count unit/label, reason_code/summary, permitted evidence/contradictions/supporting
Decision IDs, limitations/configuration statuses, retrieval/model/policy/mapping versions,
review_context_version, context_fingerprint, generated_at and audit_reference. Unavailable
or uncomputed measures are null. Reasons distinguish absent/insufficient/incompatible/below-
threshold history, contradictions, unknown correspondence, unsupported corrections, stale/
corrupt lineage, incomplete index/query cache, provider failure and deadline/access failures.

One bounded Stage7 service invocation (limit20/offset0), no internal HTTP/pagination/embedding
or RQ enqueue from recommendation GET. Query preparation remains Stage7 background work:
the existing Similar Decisions UI requests its bounded query job; pending cache is explicit.
Similarity and new recommendation reads share the existing actor120/min ceiling (not120 each).
A Stage7 READY result alone is insufficient: every scoped compatible effective Decision
must have an active-version vector. An explicit non-INDEXED skip cannot hide a possible
contradiction; Stage8 returns UNAVAILABLE/INDEX_COVERAGE_UNCERTAIN without partial evidence.
This stronger gate leaves the public Stage7 retrieval semantics unchanged.
A monotonic1500ms protective deadline updates remaining statement/lock time before every SQL;
it is distinct from the mandatory p95<=1s/10sessions engineering target. Migrations and ordinary
manual Decision SQL keep their previous defaults. No capacity100k/cold-OS/industrial claim
is implied by a test-only10k fixture or a PostgreSQL buffer restart.

## Audit receipt and human confirmation

After closing its read-only snapshot, GET may persist one deduplicated immutable audit receipt.
Actor+case+basis fingerprint form its stable ID; identical reads reuse original timestamp.
Payload <=64KiB holds exact versions/policy, used scoped mapping slice, <=20 evaluated
IDs/scores/context hashes/groups/exclusion reasons and current action references. No raw
payload, human reason, secret or vector is copied into audit. Immutable referenced Decisions,
artifacts and frozen contexts allow reconstruction. Corrupt/malformed receipts fail closed;
audit failure does not prevent an independent manual Decision.

UI «Использовать предложение в форме» merely fills a current source selection. The person
must enter a reason, inspect the confirmation dialog and explicitly save. Beginning review
changes the token, clears the old reference/draft and reloads the recommendation. Manual
override clears the optional reference; the server independently derives MATCHED/OVERRIDDEN
if a valid reference accompanies another human choice. No client accepted flag is trusted.

Existing POST Decision accepts optional recommendation_reference UUID. Existing permissions,
Origin, token/head/version, value validation, persistent idempotency and explicit confirmed=true
all remain mandatory. New referenced submissions additionally require the existing
recommendation.accept_as_decision. Under a short exclusive cooperating-write gate the server
refreshes auth/ORM and recomputes evidence/config fingerprint; stale references return409.
Exact already-committed retry returns the original receipt after current auth/scope/permission/
payload checks, before Redis/rate/recomputation. The new Decision stores server-derived receipt
metadata in additive JSON; no old Decision or source value is rewritten and no migration is added.

Ordinary review/Decision, scope/logout and retrieval activation use a shared gate before row
locks; they remain parallel except while atomic optional receipt validation commits. Waits
are bounded. No-reference Human Review remains independent of recommendation/provider/Redis.
Direct operator SQL bypassing this application protocol requires quiesce; advisory locks do
not defend against DB superuser changes. Actual concurrency/restart/NFR tests remain release gates.

## Themes and route recovery

The shared labelled Светлая / Тёмная control is available on login and every application screen.
An external same-origin early script validates only light/dark and applies presentation before
React, preserving strict CSP. System preference applies initially; local explicit preference wins.
Blocked storage retains a session choice without breaking the UI. Switching never reloads or
remounts the current review form. Shared CSS tokens cover surfaces/controls/status/focus and
reduced-motion. URL fragments retain only validated page/UUID identifiers for reload/navigation;
server authentication/scope still controls all reads. Unsaved reason/password is not persisted.

Gallery acceptance captures every main scene in light/dark at1440 and390px, checks WCAG/Axe
in both modes and all five existing responsive widths. Real Stage8 browser path separately
imports five independent file pairs, confirms actual Decisions, retrieves/proposes current
value, visits actual precedent and returns/reloads the same dark-themed route, preserves
the draft during theme changes, confirms through the existing dialog, then exercises manual
override and contradictory subsequent history. These are required checks, not a PASS claim.

## Acceptance still required

All issue #29 §11 gates, independent source/security/product review and targeted tests,
100/1k/10k actual-history performance at10sessions, real HTTPS restart/error recovery,
production unavailable smoke and green exact-final-HEAD push/PR CI are required. The14 carry-over
dispositions/owners/criteria are preserved in the approved proposal; results belong in the
stage acceptance report. #17/#18/#20 remain open and Stage9 remains excluded. Stop at READY
TO MERGE only after verified acceptance; no automatic merge.
