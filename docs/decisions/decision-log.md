# Forest Keeper — decision log

## Accepted / current decisions

### Product boundary
Forest Keeper is a layer over existing enterprise systems, not a replacement for them.

### Prototype write boundary
Prototype 0.1 reads customer/source data and writes only to FK internal storage. No writeback to 1C/ERP/CRM in prototype 0.1.

### Raw data and provenance
Raw source data must be retained. Normalized values do not overwrite originals.

### Canonical representation
Canonical representation exists to compare heterogeneous source data. It does not establish truth.

### Master data
FK ships with a preconfigured baseline master-data representation for supported domains. Customer configuration may adapt it to established standards and processes.

### Authority
Authoritative Source may be configured down to attribute level. NOT_DEFINED is a valid state.

### Human decision
When FK cannot establish truth safely, it must route the case to a person. AI confidence is not authorization.

### Decision Registry
Human-confirmed decisions are stored in a structured internal registry with the conflict context, source values, selected outcome, actor, time, reason and provenance where applicable.

### Recommendations
Recommendation Engine may retrieve similar confirmed decisions and propose a handling for a new case, with evidence/explanation. The final decision remains human in prototype 0.1.

### AI memory
The LLM is not the system of record for enterprise knowledge. Decisions, rules, mappings, canonical/master models and audit data are structured persistent data.

### Interface
Home screen represents the health/state of the enterprise information environment. Do not design it as a generic assigned-task dashboard.

### Git and portal
Git is the engineering source of truth. The future Forest Keeper Project Portal should render repository-backed content and must not become a separate competing documentation source.

### Adaptive client model
FK starts from a vendor baseline master-data/rules template. During implementation the customer may adapt it. During operation, confirmed user decisions are stored and used to recommend handling of similar future cases. Repeated patterns may trigger a proposal to formalize a new customer rule. FK must not silently change the customer's rules; formal rule/template changes require human approval.

### AI purpose
AI/LLM is a functional part of the adaptive recommendation loop. It uses structured customer context and retrieved confirmed decisions to explain and recommend. It is not a decorative feature and is not the system of record.

### Local AI baseline
MVP local LLM baseline is `Qwen/Qwen3-8B-GGUF`, artifact `Qwen3-8B-Q4_K_M.gguf`, served through `llama.cpp`. MVP embedding baseline is `Qwen/Qwen3-Embedding-0.6B` at 1024 dimensions, used through `sentence-transformers` with PostgreSQL + pgvector. Exact upstream revisions and packaging rules are pinned in `models/model-manifest.yaml`. Model weights are release artifacts outside Git. Replacing model family/revision/quantization/embedding dimension requires an explicit compatibility decision and tests.

### Client access
**Web Client is the primary client for MVP and the default Forest Keeper user interface.**
It runs in the browser and communicates with FK Server only through HTTPS/API Gateway.
Superseded by the explicit 2026-10-21 Web-only decision below: Desktop Client is excluded from the current product direction.
Backend/API remains separated from frontend without committing to a second client.
Neither client has direct access to PostgreSQL or internal services.

### Installation model
Deliver a conventional Forest Keeper Server Setup experience to the customer while using containerized deployment internally. Installer should support offline enterprise installation and hide Docker/container mechanics from ordinary administrators.

### Licensing
Add License Service to FK Server. Support online and offline signed licenses. Use a separate internal supplier-side FK License Generator. Private signing key stays only with supplier; customer receives license file and public-verification capability.

### License expiry
Recommended lifecycle is ACTIVE → GRACE_PERIOD → READ_ONLY. Expired license must not make customer-owned data inaccessible. Admin access, audit, export and license renewal remain possible.

### Updates
Add Update Service with online/offline modes, signed update packages, compatibility checks, backup, DB migration, health checks and rollback.

### Release/versioning
Git remains source of truth. Version product, DB migrations, rules/config, connectors, tests and documentation. Release artifacts must be traceable to Git tags.

### Separation of duties / ADMIN
ADMIN is a technical/system administration role. ADMIN alone does not authorize a user to make business Decisions on Conflict. Business decision authority requires the applicable REVIEWER or DATA_OWNER permission according to `docs/security/access-control-matrix-v0.1.xlsx`. A user may hold multiple roles.


### Canonical data model
For MVP development, docs/data-model/data-model-v0.2.md is the canonical data-structure and enum reference. Forest_Keeper_Data_Model_v0.1.xlsx is retained only as historical design material and must not override v0.2, Object Lifecycles, API or Access Control Matrix.

### MVP recommendation similarity
MVP 0.1 uses a hybrid similarity approach: structured filters/SQL for deterministic narrowing plus pgvector embeddings for semantic similarity of Decision context. Recommendation must remain explainable and must degrade to the deterministic/rule path if AI/LLM is unavailable.

### Decision Registry schema baseline
The logical Decision Registry schema is fixed by docs/data-model/data-model-v0.2.md for MVP. Physical indexes, JSONB decomposition and query tuning remain implementation details and may evolve without changing the API/business contract.

### MVP engineering NFR baseline
`docs/requirements/functional-nonfunctional-v0.3.md` is the mandatory engineering acceptance baseline for MVP development. Its performance/capacity values are development targets, not contractual customer SLA. Production SLA, RPO/RTO and pilot-scale limits are established after benchmark/pilot evidence.

### 2026-10-19 — MVP browser session authentication

The MVP client is the web browser; application services run on the server. Local authentication uses a server-side session and Secure/HttpOnly/SameSite=Strict cookie only. Login returns user information without the session identifier in JSON. Bearer authentication and a separate API-client login flow are outside the agreed MVP scope and have been removed. Login and state-changing cookie requests require an explicitly allowed Origin, including rejection of absent and `null` Origin. Future non-browser authentication needs a separate explicit decision.

### 2026-10-19 — Stage 2 file import contract refinements

Issue #7 authorizes a file-only import subsystem. The canonical SourceSystem specifies source_type as an Enum without a complete value set; the Stage 2 API refines it to FILE and ONE_C (the existing API example), with no source write-back. CSV/XLSX/XML are file formats, not new lifecycle states. The ONE_C adapter initially accepts the documented synthetic XML export profile; production export compatibility must be checked against pilot samples.

Duplicate identity is `(SourceSystem, SHA-256 of saved bytes)`. A repeated upload returns HTTP200 and the existing primary ImportBatch, without enqueueing another job. Retry is explicit, permission import.retry, and creates a new ImportBatch with retry_of_id and the same original; historical batches/raw/audit remain. New uploads return201 after accepting the original and batch, with asynchronous processing status. Add paginated GET imports and GET imports/{id}/records to meet browser raw/provenance visibility. Parser/storage resource bounds and operational recovery are specified in docs/development/import.md and do not change canonical ImportBatch transitions.

### 2026-10-20 — Stage 3 normalization representation (issue #12)

Use the existing AnalysisRun and its canonical lifecycle for normalization only. Matching/conflicts are not executed or reported as computed. Existing analysis.run / analysis.view permissions apply. During Stage 3, template_id identifies an immutable, versioned application mapping profile; it does not introduce CustomerTemplate activation or a new persistent business mapping entity. Store the complete validated mapping snapshot, SHA-256 and engine/rules version with each run. Profiles are release configuration, not executable expressions or user-uploaded code. The supplied Material and capacity profiles are explicitly synthetic; the real first pilot domain remains open.

A pre-match CanonicalEntity represents exactly one RawRecord under one mapping/rules fingerprint. It establishes no cross-source identity. Same raw/fingerprint reuses append-only EntityValue/entity facts via deterministic identifiers; explicit reruns create new AnalysisRun history and technical run/output associations. A different fingerprint creates new representation facts and preserves all previous results. No new business status enum is introduced: canonical docs list CanonicalEntity.status without defining its values/lifecycle, so Stage 3 reserves it as NULL, with no manual transitions. Later matching/lifecycle work needs an explicit compatible change; do not silently treat these representations as matched entities.

### 2026-10-20 — Stage-gate architecture check and evolving Gold Reference

Every MVP stage transition must include an explicit **architecture/intent gate** before the next stage is accepted or started. The check is not limited to green tests: implementation must be compared with the product intent, architecture, canonical data model, lifecycles, trust boundaries, human-in-the-loop rules and the current Decision Log. Any drift must be corrected or explicitly accepted as a new decision before proceeding.

Forest Keeper's "Gold Reference" is a **versioned, configurable customer reference/baseline**, not an immutable universal truth and not the same thing as the transient canonical representation. It may evolve during operation as a result of explicitly confirmed human decisions and later formalized customer rules/templates. The system must never silently mutate this reference from AI output, similarity, or one-off observations.

Any Gold Reference change must be:
- explicitly approved by an authorized human under the applicable RBAC/workflow;
- versioned and immutable as historical versions;
- fully auditable: actor, time, reason, previous version, new version, affected domain/entity/attributes/rules and provenance/decision references where applicable;
- reversible only by creating/activating another explicit version, not by rewriting history;
- accompanied by an impact calculation identifying which existing assessments, matches, conflicts, recommendations, decisions-derived criteria or other dependent results may no longer be valid under the new reference.

Before activation, the UI must clearly warn the user that changing the Gold Reference can change evaluation criteria and therefore may require re-evaluation of previously processed data. The warning must present the impact scope when it can be calculated.

After activation, dependent derived results must not silently continue to appear current. They must either be re-evaluated under the new Gold Reference or be explicitly marked **stale / based on previous reference version** until re-evaluation. Historical results remain reproducible against the exact Gold Reference/rule/template version that produced them.

The architectural principle is therefore:

`human decision → structured confirmed history → optional proposal to formalize → human approval → new Gold Reference/rule/template version → impact analysis → explicit re-evaluation/stale marking`.

This rule applies to future CustomerTemplate/Rule/RuleSuggestion implementation and must be checked at every stage gate so intermediate stages do not accidentally hard-code the Gold Reference as immutable truth.

### 2026-10-20 — Gold Reference history and rollback

Gold Reference / CustomerTemplate / formalized Rule state must be stored as **append-only version history**. Human decisions can be mistaken, situational or later reconsidered; therefore an approved change must never overwrite the previous reference in place.

Requirements:
- every Gold Reference version is immutable after activation;
- each version stores parent/previous-version reference, author/approver, activation time, reason, structured diff, linked supporting Decisions/RuleSuggestions where applicable, and affected scope;
- one version is marked active for a given applicable scope; historical versions remain addressable and auditable;
- rollback is implemented by creating/activating a new version whose content is based on a previous historical version; do not delete or rewrite the intervening history;
- rollback requires the same authorization, audit and impact-analysis rules as any other Gold Reference change;
- activation/rollback must signal that evaluation criteria may change and must calculate/mark dependent derived results for re-evaluation or stale status;
- historical Decisions and derived results retain the exact Gold Reference/rule/template version that was active when they were created;
- the system must be able to reconstruct the sequence of Gold Reference versions and explain why each transition occurred.

A rollback is not a claim that the reverted-to version was always correct. It is a new explicit human-approved state transition preserving the full history of intervening versions.

### 2026-10-20 — Stage 4 matching execution and conservative identity policy

Stage4 uses technical MatchingRun infrastructure with the existing AnalysisRun NEW→QUEUED→PROCESSING→COMPLETED/FAILED lifecycle; completed normalization AnalysisRun origins/results remain unchanged. Each execution freezes two completed normalization run IDs, their mapping/engine lineage, matching profile snapshot/hash/engine and explicit threshold policy. MatchCandidate keeps exactly the canonical fields and POSSIBLE_MATCH→MATCHED/NOT_MATCHED lifecycle; a technical run/pair association enforces unordered uniqueness inside an execution. Explicit reruns create new candidate history; duplicate delivery never overwrites manual review. confirmed_by is a human only, and match.review is the existing REVIEWER/DATA_OWNER permission; ADMIN alone cannot confirm.

The synthetic Material profile uses an explicit composite code+name identity rule. Repeated keys, conflicting strong signals and missing/invalid identity inputs cannot auto-match. Rule/fuzzy scores remain POSSIBLE_MATCH without an accepted production threshold; no fuzzy/weighted runtime auto-match threshold is introduced. Declared strong-key disagreement can reject a candidate. Offline threshold sweeps are evidence for a later explicit decision, not production defaults. No physical entity merge or Stage5 Conflict is introduced.

Blocking uses declared identifiers/composite identity and name prefix/tokens, bounded buckets and candidate degree on both sides, with deterministic ordering and explicit incomplete-coverage diagnostics. Omitted pairs are never declared NOT_MATCHED. Profiles/engine/input versions remain historically addressable; read views indicate previous-profile results when the current profile hash differs. Gold Reference is explicitly unconfigured, not a synthetic immutable customer baseline; its future version dependency can be added without rewriting historical evidence. Full approved Gold activation/rollback/impact workflow remains Stage11–12.

### 2026-10-21 — User-facing name: Forest Codex

The user-facing product term for the versioned customer reference/baseline previously described as "Gold Reference" is **Forest Codex**.

Definition:
- **Forest Codex** is the versioned customer-approved set of reference values, rules, criteria, mappings and evaluation settings used by Forest Keeper to interpret and assess data.
- Example UI label: `Forest Codex v5`.
- Historical versions remain immutable and auditable.
- A result must retain the exact Forest Codex version used for its evaluation.
- If a result was evaluated under an older Codex than the currently active one, the UI must indicate that fact and, where impact analysis shows relevance, mark the result stale or require re-evaluation.
- Forest Codex is not AI, not the matching/scoring engine, not source truth, and not an immutable universal truth.
- The term must not be confused with OpenAI Codex; in product/UI context, "Forest Codex" always means the customer reference baseline.

Existing documentation references to "Gold Reference" are a transitional internal alias and should be migrated to "Forest Codex" in user-facing and newly edited documentation. Historical documents may retain the older term where changing them would rewrite history.

## Open decisions
- Exact first pilot domain.
- Thresholds for automatic entity matching versus human review.
- Exact public/private portal boundary.
- Production deployment topology for first pilot.


### 2026-10-21 — Desktop Client excluded from product scope

Forest Keeper will **not** develop or maintain a native Desktop Client as part of the current product direction.

Decision:
- Web Client is the sole supported end-user interface direction;
- Desktop Client is not merely deferred or deprioritized; it is removed from roadmap/scope;
- no desktop-specific installer, device-trust client, update channel or parallel UI contract should be designed;
- backend/API may remain cleanly separated from frontend as good architecture, but this must not be interpreted as a commitment to a future native client;
- any future return of a Desktop Client requires a new explicit product decision based on a concrete customer/security need.

Rationale: a native client currently adds installation, update, compatibility and support cost without delivering product capability that the Web Client cannot provide for the intended Forest Keeper workflows.

### 2026-10-21 — External review contract and matching policy

User-confirmed review target: Saturday **2026-10-24**, Europe/Moscow. The required product path remains two file sources → normalization → matching → conflict → human Decision → persistence/restart → similar confirmed Decision retrieval → evidence-backed recommendation. Documentation must distinguish implemented main behavior from this target. Missing modules remain explicit blockers for issue #18.

Public datasets with verified provenance and usage terms may be used for review. The USGS earthquake snapshot is a technical demonstration, not selection of the first industrial pilot domain, not a claim of independent source systems, and not an Entity Resolution gold benchmark.

Fuzzy/weighted matching does not automatically confirm identity. Ambiguous similarity remains POSSIBLE_MATCH for authorized human review. Automatic confirmation is permitted only by an explicitly agreed, unambiguous exact-key rule without contradictory strong signals. No numeric production threshold is implied by this decision. Matching review and the later Conflict Decision remain distinct persisted actions.

The Qwen repositories, pinned revisions, quantization and 1024-dimensional embedding baseline are unchanged. Checked upstream artifact checksums replace packaging placeholders. A versioned artifact lock and acquisition/verification command prepare model files; they do not claim inference readiness, offline package signature verification or integration with Decision Registry. AI runtime/model-info/smoke tests remain acceptance blockers until implemented.

### 2026-10-23 — Stage 6 immutable human decisions (issue #25)

The later explicit Stage6 issue combines Human Review and Decision Registry, superseding the older plan's separate stages6/7 for this iteration. It excludes retrieval/recommendation/AI/write-back. Canonical outcomes are unchanged: SELECT_VALUE, ENTER_VALUE, INSUFFICIENT_DATA, DEFERRED. Source A/B are selections of frozen value references; no false-positive outcome is invented.

Decision facts are insert-only, with an immutable supersedes_decision_id. ACTIVE/SUPERSEDED and the effective head are derived from successor existence. Unique first/head lineage and a locked Conflict row serialize concurrent submissions. Persistent actor+Conflict+idempotency-key identity rejects a changed payload and returns the original receipt on an authorized identical retry. Review-context tokens bind immutable evidence and the current lifecycle/version/head.

An explicit review-start POST, not GET, enters IN_REVIEW. Correcting the same case may explicitly enter IN_REVIEW from RESOLVED/INSUFFICIENT_DATA while retaining the prior effective Decision until a new superseding Decision commits. New imports do not reopen old cases. SELECT_VALUE/ENTER_VALUE resolve; INSUFFICIENT_DATA preserves the canonical terminal review result; DEFERRED remains IN_REVIEW. Deferred database integrity checks require an effective Decision for final states and consistency of its immutable history. Only lifecycle/version/effective-reference fields of Conflict may change; evidence remains immutable.

Minimal persisted domain grants complement existing action permissions. User.data_domains defaults to [] for new accounts; an explicitly assigned ["*"] means all domains in this instance. Migration preserves legacy instance-wide data access as an explicit grant; no scope is inferred from ADMIN/REVIEWER role names. Scope assignment uses existing user.manage plus role.assign, recent authentication and audit. New Conflict/Decision reads and review writes enforce scope; this does not advertise a complete new multitenant ingestion isolation scheme. ADMIN remains a technical role without implicit business authority. Scope and permission are rechecked on submission.

Corrected values are allowed only when frozen canonical kind/unit are supported and unambiguous; no numeric business range is invented. Null/missing/invalid/unknown values cannot be selected as valid truth; the user can explicitly record insufficient data or defer. Input/trace and historical references remain inside the immutable Decision; raw and normalized source facts never change. Decision saves require a human reason and explicit client confirmation. No service/AI actor creates decisions.

### 2026-10-23 — Stage 7 retrieval policy before implementation (issue #27)

Stage 6 is accepted in main at 0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852 (PR #26;
merge CI 39947944543 passed). Actual Stage 7 is Similar Decision Retrieval, the older
roadmap's Stage 8. Recommendation/AI/LLM/runtime/write-back remain outside this stage.

Eligible precedents are immutable SELECT_VALUE/ENTER_VALUE facts which are the current
effective head of a RESOLVED Conflict, have no successor and have validated frozen
evidence. INSUFFICIENT_DATA, DEFERRED, superseded and IN_REVIEW cases are excluded.
Disabled historical actors do not erase their legitimate human decisions. Caller
authentication, existing conflict.view and decision.view permissions and explicit
domain grants are checked afresh. No new permission or inferred ADMIN scope is added.
Scope is applied before counts, compatibility and ranking; restricted empty pools say
NO_ACCESSIBLE_PRECEDENT without revealing whether foreign history exists.

Compatibility requires exact domain, entity type, attribute, conflict type, canonical
value kind and unit; unknown or ambiguous kinds/units fail closed. Normalized observations
are sorted semantically, without transient IDs, timestamps, reasons or selected outcomes
as embedding signals. Source type/role is frozen for new facts; absent legacy metadata
remains UNKNOWN rather than being reconstructed from today's source configuration.

The provider contract is 1024 dimensions. The pinned future Qwen manifest is unchanged.
There is no accepted production provider: production returns explicit UNAVAILABLE and
preserves Registry/Human Review. Issue #27 §8 permits a deterministic test provider;
it requires explicit development/test deployment plus explicit opt-in, uses a separate
model ID and exact revision, and accepts only declared frozen synthetic profiles.
Test vectors are infrastructure evidence, not production semantic-quality evidence.
No network model calls, weights or AI runtime are introduced.

Retrieval uses exact filtered pgvector cosine search (no approximate recall claim),
score clamp(1-distance,0,1), full precision threshold >= 0.85, API six decimals and UI
two decimal percent. Default top-N 5, maximum 20, offset 0..100; ties use distance ASC,
decided_at DESC, Decision ID ASC. Threshold is versioned server configuration; clients
cannot override it. Version changes create new immutable derived artifacts; explicit
audited operator activation leaves old versions readable. No similarity operation
creates a Decision, reopens a Conflict, proposes an action or changes source data.

Backfill is server-operated, background, bounded and restartable. Per-version locking
and unique Decision/version checkpoints prevent duplicate work; an anti-join detects
late commits rather than trusting a timestamp watermark. Live scoped coverage is
checked on every query, so partial indexes never masquerade as complete results.
Technical runs reuse AnalysisStatus; checkpoint outcomes are derived metadata, not
new business lifecycle states. Configuration, activation, run lifecycle and security
denials are audited; normal similarity GETs do not log input, vectors or human reasons.

Independent review refinement: the retrieval transaction is read-only REPEATABLE READ
starting before authentication, so permissions, eligibility, counts, coverage and rank
share one snapshot. A concurrent later commit is visible on the next request, never as
a partial READY pool. Query embeddings are also background jobs (FK-NFR-PER-004): a
missing immutable context/version cache returns INDEXING/QUERY_CONTEXT_PENDING and
queues bounded technical preparation without changing business facts. GET performs no
embedding calculation. Binary vector fingerprints are checked before thresholding,
including candidates which would otherwise disappear below threshold. The API has a
1500ms local statement timeout and an authenticated 120 reads/minute limit; migrations
and Decision saves do not inherit the retrieval timeout.

The PostgreSQL17 capacity gate exposed underestimation of the cross-table effective-head join. Retrieval now materializes narrow scoped eligibility once, joins artifact metadata once, scores once and loads full historical JSON only for top-N. Its read transaction locally prefers hash joins and disables JIT startup; ordinary API/migration connections keep their defaults. The 1500ms protective statement deadline permits rare outliers while the measured p95 target remains <=1s at10sessions. Null-free predecessor exclusion preserves superseded policy. Actual vectors satisfy coverage directly; immutable skip checkpoints are consulted only for missing representations.

Stage 7 CI idle recovery correction (23 October 2026): cap ForestWorker blocking dequeue by maintenance_interval (minimum1s), preserving120s worker TTL/150s readiness margin. RQ default idle105s could postpone nominal30s autoindex past90s retrieval acceptance. New real idle-worker regression fails before correction and passes afterwards without unrelated queue traffic. Decision save remains independent of Redis/retrieval jobs; no lifecycle, permission, provider or scoring change.


## Proposed decisions — not accepted

### 2026-10-24 — Stage 8 architecture and numerical demo policy (issue #29)

**PROPOSED / OWNER_APPROVAL_REQUIRED.** Issue #29 §6.7 requires numerical policy approval before business-logic implementation; §13 requires the architecture/Decision Log proposal first. The user instruction to start Stage 8 authorizes preparing this proposal, not inventing approval of previously unspecified thresholds.

[Concrete architecture/policy proposal v1](../development/stage8-recommendation-proposal.md) records every contested choice, exact planned file/API/schema changes, golden fixtures and all 14 Stage 7 carry-over dispositions. Proposed demo policy: complete <=20 eligible above-threshold pool, >=5 independent provenance groups, unit group weight, 100% agreement/zero contradiction, explicit approved source correspondence; ENTER_VALUE remains contextual. Confidence is an absolute independent-group count, never probability or synthetic score. Production remains fail-closed. Proposed stateless service plus bounded audit receipt has no new SQL table/migration; existing human-confirmed Decision POST is the only write path. These are proposals, not current runtime behavior.

Owner approval: **pending**. Approved policy version/content digest/reference: **none**. No positive recommendation business logic is implemented or enabled by this entry. Any change after approval requires a new version and explicit rationale/fixtures; independent review is required before Stage 8 acceptance.

Entry gate: Stage 7 accepted by owner via PR #28, main merge `c927af513d29d83bd53b1b6522efccb42b5a1341`, exact merge CI 40079346518 SUCCESS. Actual numbering is Stage 6 Human Review+Registry, Stage 7 retrieval, Stage 8 recommendations, next Stage 9 AI/LLM. Historical roadmap numbers remain historical; #17/#18/#20 remain open.


## Accepted Stage 8 policy — 25 October 2026

The repository owner explicitly approved all eight product-policy points in this chat:
**«Согласен со всеми пунктами.»** This follows the complete plain-language explanation
of minimum five independent provenance groups, conservative correlation, unanimity/zero
contradiction, explicit source correspondence, SELECT_VALUE-only proposed actions,
absolute-group evidence strength, complete <=20 evidence window and demonstration-only
positive recommendations. This is approval to implement Stage 8, not merge authorization.

Approved policy: `stage8-demo-unanimous-v1`. Architecture proposal reviewed at
commit `1ade99f325d1710ea3d0a9734f55ac7aad3fa7b2`, content SHA-256
`9d4dd635a4366ea762c1f92a5e37f2271cbf0b4bdfdf9274a6c2f5b67b712585`.
The earlier pending entry/report is retained as historical provenance, superseded by this
explicit owner approval. Runtime policy is versioned in
`backend/app/recommendations/policies/demo-unanimous-v1.json`.

Minimum=5 groups; weight=1 per group; agreement=100%; contradictory outcomes/groups=0;
dominance margin=1. Similarity retains Stage 7 inclusive0.85 gate, never confidence.
Pool >20 above-threshold precedents abstains, no hidden pagination. Confidence=number
of independent supporting groups only when recommended, unit INDEPENDENT_PROVENANCE_GROUPS;
otherwise null. Full correlation graph includes current-case sentinel: any shared input
file hash/raw/business-key/semantic evidence joins a component; current component gives
no support. ENTER_VALUE remains historical context only. Source roles need an explicit
trusted scoped/versioned map, never A/B/name/type heuristics or implicit authority.
Production positive synthetic recommendations remain forbidden. Audit receipt cap64KiB,
shared120reads/min and total1500ms protective budget preserve the proposed bounded design.

Implement stateless deterministic service plus bounded append-only audit receipts first;
no new SQL schema/state machine or permission. New human Decisions may retain a validated
receipt snapshot in their immutable JSON context. Existing manual Human Review stays the
sole commit path and works without recommendations/provider/Redis. Atomic optional receipt
validation requires the reviewed cooperating-write gate/fresh authorization/idempotent replay
protocol and its independent race/load/recovery tests; an approved design is not proof of
its implementation. No unaccepted Rule/authority/Codex or model runtime is invented.

Full issue #29 acceptance, independent verification and green exact-final-HEAD push/PR CI
remain mandatory before READY TO MERGE. Do not merge or close #17/#18/#20; Stage 9 is excluded.


### 2026-10-25 — Stage 8 mandatory light/dark Web Client amendment

Issue #29 §14 (updated 2026-10-24T21:32:34Z) and the user's instruction «Продолжи
разработку с учётом правок в тз» add a shared light/dark theme control on all screens,
including login. Persist presentation preference locally, honor system theme before an
explicit choice, apply safely before first paint and preserve active forms/context/routes.
Browser storage failure must not break the application. Shared tokens, readable states,
visible keyboard focus and reduced-motion apply to both themes. Real browser/gallery/Axe/
responsive acceptance must cover both themes; no backend permission/evidence changes.
This is an additive Stage 8 requirement; the approved numerical recommendation policy
and the immutable historical proposal digest are unchanged.


### 2026-10-25 — Stage 8 physical representation / no-schema refinement

RecommendationResult is a stateless API outcome (RECOMMENDED/ABSTAINED/UNAVAILABLE),
not a new Conflict/Decision state or a replacement for canonical Recommendation lifecycle
CURRENT/STALE/SUPERSEDED. Bounded immutable RECOMMENDATION_EVALUATED AuditEvents preserve
provenance and act as actor/case-bound receipts. No Recommendation SQL table or migration
is introduced. Reference means the displayed recommendation, not an automatic acceptance;
MATCHED/OVERRIDDEN is derived from the actual human-selected current references.

New Decisions may add `context_snapshot.recommendation` with nested schema
`recommendation-receipt-v1`; the existing outer schema_version=1 is preserved (including its
DB constraint), as this is additive provenance rather than reinterpretation of evidence.
Absent optional references are excluded from request hashing to preserve historical retries.
Exact committed reference replay is authorized and checked before new evaluation/rate/Redis;
new evaluations consume the existing shared read quota outside the exclusive gate.
All cooperating updates use schema/database-scoped shared gate; only new optional-reference
confirmation needs exclusive gate, fresh auth/ORM and bounded recomputation. A connection
SQL hook applies remaining monotonic budget before every SQL, with cleanup at transaction end.
Audit integrity validates basis digest, event type/actor/case/reference and aware timestamp.
No advisory-lock claim is made against DB superuser/direct SQL outside the quiesce protocol.


## 2026-10-26 — Stage 9 entry and preimplementation contract

Stage8 is accepted in main through PR #30, merge
`54d3939d704bfe6aa1c943bef3e70b83b01c0527`, exact main CI40198679543 SUCCESS.
The owner instruction «Приступай к разработке 9 этапа» authorizes Stage9 implementation
on a separate branch/PR, not merge or previously unspecified semantic quality thresholds.

[Preimplementation architecture/hardware/offline/threat/gold/metrics/decision matrix](../development/stage9-local-ai-proposal.md)
is published before business code per issue #31 §10. Pinned models/1024 dimensions/Q4_K_M/
32768 context and Stage8 deterministic demo policy are unchanged. Qwen runtime development
and actual inference tests may proceed; production semantic activation/positive recommendation
policy remain blocked without explicit approved quality evidence/policy. Proposed numerical
quality targets and human-labelled evaluation set are NOT APPROVED, not achievements.
Historical Stage8 proposal/acceptance records are preserved. #17/#18/#20/#32 are not closed.
