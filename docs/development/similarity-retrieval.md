# Stage 7 — Similar Decision Retrieval

Implementation scope: [issue #27](https://github.com/SergeyRassohin/Forest-Keeper/issues/27).
Stage 6 was accepted in main via PR #26, merge `0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852`,
exact merge CI [39947944543](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39947944543).
This separate Stage 7 branch implements the old roadmap's Stage 8. It does not merge itself.

## Product and eligibility

Similarity finds actual historical human Decision IDs. It does not propose an action,
select a source, resolve a Conflict, create a Decision or alter rules/source data.
PostgreSQL Decision Registry remains the source of truth; vectors are derived artifacts.

Only SELECT_VALUE/ENTER_VALUE, current effective heads without successors, on RESOLVED
Conflicts are precedents. DEFERRED, INSUFFICIENT_DATA, IN_REVIEW and SUPERSEDED are excluded.
Starting a correction excludes even the previous ACTIVE head while review remains open.
Missing/corrupt frozen context is skipped with a persisted reason. Historical actor
account disable/removal preserves the immutable human fact; disabled callers cannot read.

Existing `conflict.view` + `decision.view` permissions and explicit `data_domains` apply.
The canonical 39 permissions and XLSX are unchanged. ADMIN receives no inferred scope
or business authority. Authentication, eligibility, scoped counts, completeness and ranking
share one read-only REPEATABLE READ snapshot. A concurrent commit appears next request.

## Provider contract and limits

Production defaults to **UNAVAILABLE**. There is no production semantic embedding runtime,
AI, LLM, external API, weight download or hidden network model call. The future pinned
Qwen baseline in the model manifest is unchanged. Issue #27 §8 explicitly permits a test
provider and production adapter interface without implementing Qwen runtime.

The separate `forest-keeper/deterministic-test-embedding` hashes normalized fixture
tokens into 1024 float32 dimensions. It is infrastructure/test evidence, **not proof of
semantic quality on enterprise data**. It requires all three settings:

```text
FK_DEPLOYMENT_MODE=test                 # or development; default production
FK_SIMILARITY_PROVIDER=test             # default unavailable
FK_SIMILARITY_ALLOW_TEST_PROVIDER=true  # default false
```

Production mode refuses the test provider even if other flags are set. Frozen matching
profiles must explicitly declare `synthetic=true`; actor names/client flags cannot enable it.
Test revision `test-v1` is SHA-256 of the literal `test-v1`, `test-v2` likewise. Exact hashes,
model ID, dimension, schema `retrieval-context-v1`, preprocessing `nfc-semantic-sort-v1`,
eligibility and score configuration form a stable version UUID/hash. New representations
coexist; no old Decision/vector is rewritten or silently treated as a new revision.

## Context and scoring

Context includes domain/entity type, unconfigured business-key class, bounded NFC/casefold
subject, attribute/conflict type, normalized sorted observations, canonical kind/unit,
frozen source types/NOT_DEFINED roles, matching/profile/engine and normalization versions,
Forest Codex/authority configuration and known unknowns. New Decisions freeze source type;
legacy absence remains UNKNOWN. Full raw payload, credentials, filenames/paths, transient
IDs, timestamps, human reason and selected outcome are not embedding signals. Context
is bounded to 32 KiB, subject 256 characters and individual values 4096 characters.

Exact domain, entity type, attribute, conflict type, kind and canonical unit filter
before/with vector ranking. No unapproved attribute-family/unit conversion is inferred.
Unknown/ambiguous units/kinds fail closed. Quantity unit support is the explicit conservative
set in the context builder; unsupported cases return unavailable instead of false certainty.

pgvector cosine distance uses `OPERATOR(public.<=>)`. Similarity is clamp(1-distance,0,1).
Threshold is versioned server configuration **>=0.85**, never client-controlled. Ranking uses
unrounded distance ASC, decided_at DESC, Decision UUID ASC. API score rounds to six decimals,
UI to two decimal percent. Default top-N 5, max 20; offset 0..100. Exact filtered search uses
B-tree compatibility indexes plus pgvector distance; no approximate/HNSW recall claim.

## Persistence, background work and recovery

Migration `0008_similarity` requires the existing `public` pgvector extension. It creates
`retrieval_versions`, singleton `retrieval_state`, `decision_embeddings`, `retrieval_items`,
`retrieval_runs` and `retrieval_queries`; it does not backfill or update business facts.
Decision/version uniqueness, FK, fixed 1024 dimensions, nonzero vectors, binary fingerprint
checks and append-only artifact guards are enforced in PostgreSQL. Model metadata lives in
the immutable referenced version; artifact input/feature hashes and context are retained.
Empty downgrade/upgrade is supported transactionally. Downgrade with Decision vectors is
refused to preserve derived audit; Decision history is never deleted. Query vectors are
rebuildable cache artifacts.

Trusted server operators use the existing execution environment, without a new HTTP admin
permission, to register/backfill and explicitly activate a version:

```bash
python -m app.similarity.cli start --revision test-v1 --batch-size 100 --activate
python -m app.similarity.cli status
python -m app.similarity.cli start --revision test-v2 --batch-size 100
python -m app.similarity.cli activate --version UUID_FROM_STATUS
```

These commands only work with the explicit test configuration above. They run **inside the
backend container** or an equivalently configured trusted environment; never expose DB/Redis
credentials in a shell history. Production provider activation is a future acceptance task.

RQ executes bounded batches (1..500, default100). PostgreSQL version/schema advisory locks
serialize duplicate delivery; each committed batch persists items/vectors/progress atomically.
Anti-join checkpoints catch late commits with older timestamps/UUIDs. A restart resumes
PROCESSING; operational failure records FAILED and a fresh run retries remaining items.
CLI status exposes progress/checkpoint/error codes. Completed/failed/start/queue/configuration
and activation events are sanitized audit facts. Old versions remain readable via trusted
database inspection for audit. Each query checks live **scoped** eligible coverage; partial
indexes return INDEXING and no partial results. The old active version serves during reindex.

`FK_SIMILARITY_AUTOINDEX=true` optionally lets the worker catch up newly committed Decisions
for the active **test** version. It defaults false. It is enabled only in the disposable
synthetic gallery/restart fixture. Decision saves have no embedding/Redis-job dependency.

Missing query context/vector cache returns INDEXING/QUERY_CONTEXT_PENDING and queues a
bounded RQ preparation job. GET never calculates an embedding. Retry then reads the immutable
context/version vector. This implements FK-NFR-PER-004 for query and historical embeddings.
The request has a 750ms local statement timeout, bounded input/page sizes and 120 authenticated
reads/minute; timeout/queue/provider failures preserve Human Review and Registry availability.
Binary fingerprints are checked across the scoped compatible pool **before thresholding**,
so a corrupt vector moved below threshold cannot silently become an honest no-precedent result.
The partial `ix_embedding_integrity` index maintains the fingerprint invariant on every
write, allowing bounded reads without rehashing 10k vectors per concurrent reader.
PostgreSQL physical storage/checksum monitoring remains responsible for raw disk corruption;
the application gate proves detection of corrupt stored rows, not repair of damaged pages.
Query-preparation failures retain a sanitized RQ FAILED status and return UNAVAILABLE;
after a 30-second cooldown the next read can request a bounded retry.

## API and UI

`GET /api/v1/conflicts/{id}/similar-decisions?limit=5&offset=0`, cookie session only.
Unknown parameters (including threshold/vector payload), invalid/huge/nonfinite bounds are 422.
No business write route exists. Direct inaccessible Conflict/Decision IDs return 404.

Response includes query context/schema/hash, retrieval version, exact model metadata,
threshold, scoped before/after/above-threshold counts, state/reason, results, limitations and
insufficient_precedent. Unavailable or uncomputed counts are null, not fake zero. Results
contain actual Decision/Conflict IDs, actor/date/outcome/value/reason, status, history/detail
reference, matched/mismatched features and frozen evidence summary.

States: READY, NO_PRECEDENT, INDEXING, UNAVAILABLE. Reasons distinguish NO_HISTORY,
NO_ACCESSIBLE_PRECEDENT, NO_COMPATIBLE_PRECEDENT, BELOW_THRESHOLD, INDEX_NOT_READY,
QUERY_CONTEXT_PENDING and operational/integrity failures. A restricted empty pool never
reveals whether inaccessible history exists. Normal GETs do not audit/log query inputs,
vectors or human reasons; security denials are audited.

The browser displays a separate **Похожие прошлые решения** section, actual IDs/history,
score, concrete context/values/unknowns and the explicit test warning. It always says:

> Похожие решения показывают прошлый опыт. Они не являются автоматическим решением текущего конфликта.

Loading, no history, no accessible precedent, indexing, unavailable and request error are
visible states. No retrieval result pre-fills or submits the Human Review form.

## Acceptance boundaries

Stage 7 requires all issue #27 tests/gates, independent review and exact-final-HEAD CI
before READY TO MERGE. It cannot establish production semantic quality, production model
runtime readiness or the complete recommendation MVP (#18/#20). A 100k Conflict queue is
not a 100k Decision benchmark. Performance evidence must count actual persisted Decisions
and vectors, disclose synthetic provenance, host/cache limits and first/warm/concurrent reads.
