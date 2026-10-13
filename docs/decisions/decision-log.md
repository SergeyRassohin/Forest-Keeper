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
Desktop Client is optional and may be introduced later for customers with special device-trust or information-security requirements.
Backend/API remains client-independent so both clients can use the same business contract.
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

## Open decisions
- Exact first pilot domain.
- Thresholds for automatic entity matching versus human review.
- Exact public/private portal boundary.
- Production deployment topology for first pilot.
