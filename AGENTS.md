# Forest Keeper — Codex project context

Forest Keeper is a vendor-neutral enterprise data intelligence and governance layer. It works over existing systems rather than replacing ERP, PLM, MDM, WMS, CRM or EAM.

## Read first
1. docs/project-context.md
2. docs/architecture/architecture-v0.2.md
3. docs/data-model/data-model-v0.2.md
4. docs/api/api-contract-v0.1.md
5. docs/architecture/technical-stack-and-module-map-v0.1.md
6. docs/development/mvp-development-plan-v0.1.md
7. docs/development/object-lifecycles-v0.1.md
8. docs/security/access-control-matrix-v0.1.xlsx
9. docs/requirements/functional-nonfunctional-v0.3.md
10. docs/testing/testing-strategy-v0.1.md
11. docs/ai/local-model-v0.1.md
12. models/model-manifest.yaml
13. docs/decisions/decision-log.md

## Prototype 0.1
Prove one narrow hypothesis: Forest Keeper can ingest data about the same entities from two sources, normalize it, resolve entity identity, detect conflicts, explain them, obtain a human decision, store that decision, and use confirmed decisions to recommend handling of similar later cases.

Prototype boundaries:
- one domain;
- two sources, initially file exports such as 1C XML plus Excel/CSV;
- source systems are read-only;
- no autonomous production-data modification;
- human decisions are stored in Decision Registry;
- recommendations may use confirmed prior decisions;
- AI confidence is never permission to publish.

## Engineering invariants
- Preserve raw source values and provenance.
- Normalization is not truth.
- Authoritative Source may be defined per domain/entity/attribute and may be NOT_DEFINED.
- If truth cannot be determined, return UNKNOWN / human review.
- AI is not the enterprise memory. Structured rules, mappings, decisions and audit history are.
- Security-critical changes require independent verification.
- Git is the engineering source of truth.
- Prefer a monorepo and version code, DB migrations, rules, models/config, connectors, tests and documentation.
- Data structures and canonical enum names must follow docs/data-model/data-model-v0.2.md.
- Object state transitions must follow docs/development/object-lifecycles-v0.1.md. Do not invent new states or transitions silently.
- Authorization must follow docs/security/access-control-matrix-v0.1.xlsx. Do not infer permissions from role names.
- ADMIN is a technical/system administration role. ADMIN alone does not grant authority to make business Decisions; the user must also hold REVIEWER or DATA_OWNER permission as defined by the access matrix.
- MVP engineering quality/performance targets are defined by docs/requirements/functional-nonfunctional-v0.3.md and are mandatory acceptance baselines unless a newer explicit decision overrides them.
- Local AI baseline must follow docs/ai/local-model-v0.1.md and models/model-manifest.yaml. Do not silently substitute model family, revision, quantization or embedding dimension.
- Model weights are external release artifacts and must never be committed to Git.

When documents conflict, prefer the newest explicit decision in docs/decisions/decision-log.md and flag the conflict rather than silently guessing.

## Mandatory stage gate
At the boundary between MVP stages, do not rely on test status alone. Before a stage is accepted and before work on the next stage begins, verify the implementation against product intent, architecture, canonical model, lifecycles, security/trust boundaries, human-in-the-loop constraints and the current Decision Log. Record and resolve any drift.

Treat the customer Gold Reference/baseline as versioned and configurable, not as immutable truth. It may change only through explicit authorized human approval. Every change must be logged/versioned, historical versions preserved, impact on dependent evaluations calculated where possible, and the user warned that criteria/results may change. Results based on an older Gold Reference must be re-evaluated or clearly marked stale; never silently reinterpret history under the newest version.


## Additional mandatory architecture context
- Web Client is the primary client for MVP and the default user interface.
- Web Client is the sole supported end-user interface. Desktop Client is excluded from scope/roadmap by the explicit 2026-10-21 decision; any return requires a new product decision.
- Backend/API must remain independent from client type.
- Adaptive behavior is a core FK feature: vendor baseline template → customer configuration → confirmed human decisions → similar-case retrieval → explainable AI recommendation → optional proposal to formalize a new rule → human approval.
- Never implement "self-learning" as silent automatic rule mutation.
- Add License Service and Update Service as first-class server components.
- Supplier-side FK License Generator signs license payloads with a private key; customer side only verifies signatures.
- Support online and offline licensing/update flows.
- Default license-expiry behavior should preserve customer data access and administration while restricting new processing after grace period.
- Deployment should present a conventional enterprise installer while containerization remains an implementation detail.
