# Forest Keeper — MVP v0.1 Requirements

## Goal
Prove that Forest Keeper can ingest data about the same entities from two existing customer sources, normalize and match them, detect conflicts, obtain a human decision, store that decision, and use confirmed prior decisions to recommend handling of similar later cases.

## Initial customer profile
The first realistic pilot may be a small company with a small 1C installation such as 1C Accounting / warehouse-related configuration, plus a large amount of Excel files and possibly a free or lightweight CRM.

## In-scope data sources
Initial MVP supports file-based ingestion from:
- 1C exports, especially XML;
- Excel;
- CSV;
- XML from other systems.

CRM integration is deferred unless a simple export is available.

## Functional requirements
1. Preserve original uploaded files and source values.
2. Parse rows/objects and attributes from each source.
3. Map source-specific field names to a canonical internal model without forcing the customer to rename fields in their source systems.
4. Normalize comparable representations such as units, dates, whitespace, casing and equivalent attribute names.
5. Match records from different sources that represent the same real-world entity.
6. Detect attribute conflicts, missing values, duplicates, format violations, rule violations and suspicious values.
7. Send ambiguous cases to Human Review.
8. Allow a user to choose one source value, provide another value, or mark insufficient information.
9. Store confirmed human decisions in Decision Registry with object, attribute, source values, chosen result, user, timestamp and explanation when provided.
10. For later similar cases, query prior confirmed decisions and present a recommendation with an explanation and confidence/evidence.
11. Maintain an audit trail of uploads, transformations, matches, conflicts, recommendations and human decisions.

## Hard MVP boundaries
- Customer source systems are read-only.
- Forest Keeper does not write back to 1C, Excel, CRM or production systems.
- No autonomous modification of production data.
- AI confidence is not permission to publish or change customer data.
- If truth cannot be determined, the system returns UNKNOWN / human review rather than inventing certainty.
- The canonical model is an internal FK model, not a demand that the customer redesign existing processes or fields.

## AI positioning
Forest Keeper may legitimately be described as a system that learns from confirmed expert decisions and uses accumulated experience to recommend handling of similar later cases.

Enterprise memory itself must remain structured and inspectable: rules, mappings, Decision Registry, audit history and model configuration. AI is a consumer of that knowledge, not the only place where it exists.

## Success criteria for prototype 0.1
A demo is successful when two customer exports containing overlapping entities can be loaded and Forest Keeper can visibly demonstrate this complete loop:

`ingest → preserve raw data → normalize → match → detect conflict → human review → store decision → use prior decision in a later recommendation`
