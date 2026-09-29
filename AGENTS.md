# Forest Keeper — Codex project context

Forest Keeper is a vendor-neutral enterprise data intelligence and governance layer. It works over existing systems rather than replacing ERP, PLM, MDM, WMS, CRM or EAM.

## Read first
1. docs/project-context.md
2. docs/architecture/architecture-v0.1.md
3. docs/decisions/decision-log.md

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

When documents conflict, prefer the newest explicit decision in docs/decisions/decision-log.md and flag the conflict rather than silently guessing.
