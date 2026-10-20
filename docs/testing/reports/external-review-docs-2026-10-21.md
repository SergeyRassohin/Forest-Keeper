# External review documentation and Qwen verification — 2026-10-21

Scope: instructions for a reviewer unfamiliar with Forest Keeper, current status consistency, download links, exact Qwen artifacts, a public-data example and checks for that example. Base: main `4c03946dc7f65804da4a96b86e72fad4fabd463e`. Final revision is the commit containing this report / the PR head; CI must be evaluated on that exact SHA.

## Result

Documentation/tooling is prepared for review. **Full MVP acceptance remains BLOCKED**, as described in [review readiness](../../deployment/review-readiness.md). Missing matching in main, Conflict/Decision/retrieval/recommendation and AI inference were not replaced with simulated results. This report does not close #18 or accept a new business stage.

## Changes

- README explains the product, current functions and the full target separately. Product Roadmap is linked. The clone command explicitly selects the review candidate branch while PR #19 is unmerged.
- Quick Start includes supported host setup, first ADMIN bootstrap, user roles, HTTPS, remote SSH access, expected migrate Exited(0), protected version endpoint, import, normalization, restart and a feedback template.
- Stage 3 status is synchronized with merged PR #13 and successful merge CI. Desktop Client is excluded consistently in AGENTS/current architecture/client-access; historical reports remain unchanged.
- MVP Plan enum/auth drift is corrected against canonical v0.2 and the Decision Log.
- Public example: 60 USGS-authored earthquake events, saved original, SHA-256 provenance, two explicitly derived CSV/XML views and a separate demo-earthquake profile. These are not independent production sources or a chosen industrial pilot domain.
- User-approved fuzzy/manual-review policy and October 24 target are recorded in Decision Log.
- Model acquisition uses pinned identities and a 14-file checksum lock; no weights are committed. The downloader validates full bytes before atomically publishing a file; corruption/oversize/concurrent-partial failure paths are tested.
- Existing dependency audit found PYSEC-2026-4320 in certifi 2026.7.22. Lock updated only that package to fixed 2026.10.19; repeat audit passed.

## Qwen verification

The original architecture baseline is retained:

| Component | Exact revision | Full weight SHA-256 verification |
| --- | --- | --- |
| Qwen/Qwen3-8B-GGUF, Qwen3-8B-Q4_K_M.gguf | 7c41481f57cb95916b40956ab2f0b139b296d974 | PASS: d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785 |
| Qwen/Qwen3-Embedding-0.6B, model.safetensors | 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 | PASS: 0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd |

Both weights were downloaded completely (5,027,783,488 and 1,191,586,416 bytes). All 14 locked files, including tokenizer/config/pooling/model cards and LLM license, passed SHA-256 checks. The exact upstream revisions were checked via the official API. Embedding config and pooling show 1024 dimensions / last-token pooling / 32768 context. The offline local `verify` action passed after the download.

This is artifact verification, **not an inference benchmark**. llama.cpp / sentence-transformers runtime versions, actual vector output, model-info, Russian structured responses, offline inference and Decision retrieval still require implementation/acceptance. Offline signature verification is not supplied by a checksum file. Embedding revision has Apache-2.0 metadata but no standalone LICENSE file; docs do not link to a nonexistent one.

## Validation

| Check | Result |
| --- | --- |
| check.sh: backend unit | 163 PASS |
| Backend integration, real PostgreSQL/Redis | 355 PASS |
| Frontend component tests | 17 PASS |
| HTTPS Chromium E2E | 9 PASS, including the public-data reviewer path |
| Artifact failure-path tests | 6 PASS |
| Total automated tests | **550 PASS** |
| Lint / format / mypy / TypeScript / frontend build | PASS |
| Docker backend/frontend build and startup | PASS on the existing test environment |
| SAST / negative security fixtures | PASS |
| New downloader/link checker Bandit | PASS; B310 scheme warnings explicitly audited against URL validation at call sites |
| Gitleaks history + staged tree | PASS, no leaks |
| pip-audit / npm audit after certifi fix | PASS, no known vulnerabilities |
| Local Markdown targets | PASS, zero missing targets |
| Active external links / exact model download URLs | **48 PASS**, [machine-readable report](external-review-links-2026-10-21.json) |
| Full model download and offline checksum verification | PASS, 14 files |

External-link scope excludes historical report/session external URLs, fragments, localhost, and reserved negative-test hosts such as evil.invalid. This is an HTTP availability/redirect check, not an audit of every upstream page's content; model identity, size and checksums are verified separately. No temporary CDN signed URL is stored in the report.

The public-data E2E uses the actual Web Client → API → RQ worker → PostgreSQL path. Both files import 60 rows and produce 240 VALID values each; known event id, magnitude and time match the documented expectations. Raw snapshots stay unchanged. E2E fixtures use temporary accounts; credentials are not committed.

## Restart persistence

The existing development stack was restarted without deleting volumes. Health returned ok. Before/after read-only snapshots agree exactly:

| Data | Count | SHA-256 of ordered snapshot, unchanged after restart |
| --- | ---: | --- |
| USGS imports (IDs/hash/status) | 2 | d40d7a91471ebe88ae5c6a24c4e678b6d18a4e4629b32fa205e3597368621bf7 |
| Public raw records | 120 | b6132232c9d185d43033bb54e9f6efc845eeac2feb5ac318778072774ea22333 |
| Normalized values | 480 | e78e1628577417c8108ccbec790a6b92168fc219f6458692671433d1e72c200c |

These are import/normalization facts, not business Decisions. No schema migration is introduced. Full fresh-machine setup by a person unfamiliar with the project, Firefox/Edge checks, production smoke, independent review and final-SHA CI are not claimed as local completed checks here. Existing stage acceptance evidence remains historical evidence for those stages.

## Architecture / Product Intent Gate

Raw/provenance and source read-only boundaries are unchanged. Canonical normalization does not establish truth or merge identities. The extra profile is immutable release configuration in a clearly demo domain. Fuzzy matches remain for authorized manual review; ADMIN gains no business authority. AI is neither memory nor an autonomous writer. Forest Codex history/versioning/impact/stale rules remain required for future stages. Backend remains a modular monolith with a browser UI. Stage 5/11 are not implemented prematurely.

Remaining blockers and independent review are visible in [review readiness](../../deployment/review-readiness.md). The PR is reviewable; a green CI result alone does not establish the full product path.
