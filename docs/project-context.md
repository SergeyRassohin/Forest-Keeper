# Forest Keeper — consolidated project context

## Product
Forest Keeper (FK) observes an enterprise information environment and helps people make decisions about it. It connects to approved heterogeneous sources, links records referring to the same real-world entities, detects data-quality problems and conflicts, preserves provenance, explains findings, and routes ambiguous cases to people.

FK is not intended to replace ERP, PLM/PDM, MDM, ESB or BI. The intended product direction combines Entity Resolution, Data Fusion, Data Quality/Observability, provenance, Impact Analysis, explainable recommendations, human decision and controlled publication.

## Human-in-the-loop
Automatic analysis may receive, normalize, match, check, detect, classify, assess risk, recommend, route and audit. Production changes require the approved workflow and an authorized human decision. A future Publisher component may write approved payloads to target systems using a restricted technical identity. The AI/LLM must never hold production credentials.

## Data model and truth
FK has preconfigured master-data representations for supported domains: recommended attributes, types, formats, units, requiredness, allowed values, normalization and checks. Customers may adapt these to their standards and processes.

The canonical model is a common internal representation for comparison. It is not a golden value. Raw values and provenance remain preserved.

Assessment can be based on configured master-data rules, customer standards, external standards, Authoritative Source policy, business rules, confirmed human-approved rules, cross-system comparison and statistical/AI patterns. AI patterns indicate anomaly, not proof of error.

Authoritative Source should normally be configurable at domain/entity/attribute scope. NOT_DEFINED is valid. If conflicting sources exist and truth cannot be established, FK must surface the conflict rather than invent truth.

## Decision learning
Confirmed human decisions are stored in a structured Decision Registry. Similar later cases may retrieve those decisions and generate an explainable recommendation. This is the basis for describing FK as learning from confirmed expert decisions without pretending the model autonomously learns truth.

## Workflow modes
Observer: analyze without blocking source systems.
Advisor: show issue, evidence, confidence and recommendation; human decides.
Post-check: inspect changes after they occur and surface significant cases.
Controlled Gateway: future selected critical flows may return PASS, WARNING or REVIEW. PASS means FK found no reason to block normal source-system processing; it does not mean FK changed data.

Deployment maturity: observe → recommend → selected Gateway.

## Prototype 0.1
Initial realistic small-company scenario: 1C (possibly accounting/warehouse), many Excel files and perhaps a simple CRM. Start with two exported sources, for example 1C XML plus Excel/CSV.

The prototype should demonstrate ingestion, raw preservation, normalization, entity matching, conflict detection, human review, Decision Registry, recommendation from confirmed similar decisions, export/audit and a simple Data Health view.

Do not initially require direct 1C writeback, OAuth/SSO, Four Eyes, HA/DR, industrial updater, OCR or broad connector coverage.

## Security direction
Reader and future Publisher identities are separate. LLM has no production credentials. Critical publication requires APPROVED. Security pipeline should include lint/type checking, unit/integration/E2E tests, SAST, SCA, secret scanning, DAST, security tests, fuzz/property tests, AI-specific red teaming, security regression and independent pentest before serious industrial deployment.

## Repository direction
Use a monorepo. Suggested top-level areas: apps, services, packages, migrations, tests, docs, deploy, scripts, portal. The future FK Project Portal should render Git-backed Markdown/YAML/JSON rather than become a second source of truth. Public and private documentation must be separated before publication.

## Interface direction
The main screen is a control panel for the state of the enterprise information environment, not a task tracker. It should emphasize Data Health, monitored entities, conflicts, rule violations/anomalies, cases requiring human attention, domain/system state and recent significant events.
