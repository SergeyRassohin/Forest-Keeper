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

## Open decisions
- Exact first pilot domain.
- Exact schema of Decision Registry and similarity features.
- Thresholds for automatic entity matching versus human review.
- Whether recommendation similarity in 0.1 is rules/SQL, embeddings, or a hybrid.
- Exact public/private portal boundary.
- Production deployment topology for first pilot.
