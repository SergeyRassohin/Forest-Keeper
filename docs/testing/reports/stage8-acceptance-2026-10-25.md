# Stage 8 — acceptance evidence, 25 October 2026

Issue [#29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29),
PR [#30](https://github.com/SergeyRassohin/Forest-Keeper/pull/30),
branch `codex/stage8-recommendations`. **Local acceptance PASS. Final delivery is gated by green exact-final-HEAD push and PR CI, recorded in PR #30. No merge authorization.**
Base accepted main: `c927af513d29d83bd53b1b6522efccb42b5a1341` / Stage7 PR #28.
Owner approved eight policy points in chat on25October; this is implementation
authorization, not merge authorization. Historical proposal pending status is preserved.

## Scope and architectural conformance

Separate deterministic service uses authorized structured history and current values.
RecommendationResult is stateless with bounded append-only audit receipts; no migration,
new canonical state, SQL Recommendation table or permission is introduced. Existing
human-confirmed Decision POST is the only business commit path. Existing XLSX39 permissions,
cookie+Origin, domain scope, tokens, immutable history and persistent idempotency remain.
The receipt bridge revalidates fresh auth/evidence under a bounded cooperating-write gate.

Policy `stage8-demo-unanimous-v1`: five independent groups,100%agreement,0contradiction,
weight1, margin1; complete above-threshold pool<=20, existing inclusive similarity>=.85.
Confidence is independent-group count, never synthetic score/probability. Shared file/raw/
business-key/semantic connected components, including current sentinel, prevent cloned support.
Explicit versioned actual-source correspondence; no source-name/order authority inference.
Current IDs are selected; historical ENTER_VALUE is not copied. Production always fail-closed.

Rules/Template/Codex are NOT_CONFIGURED, authority NOT_DEFINED. No AI/LLM, new provider,
external egress, training, RuleSuggestion, automatic resolution, source modification or write-back.
Theme/validated URL recovery are presentation-only and do not enter Decision evidence.
Stage6 Human Review+Registry → Stage7 Retrieval → Stage8 Recommendation → next Stage9 AI.
Historical roadmap numbering is not rewritten.

## Reproducible source and artifacts

Application candidate: `cd5116c4569389658bb046c197db45221c593ccd`.
Backend application tree: `0a79a1e89317b3bd3ff5da81bf64168ae1fde191`.
Frontend source tree: `cf5309eac8b8f2929c98b975eadf966da3243282`.
Subsequent delivery commits contain reports/gallery/documentation only; the final CI
checks the complete final Git HEAD. Exact delivery SHA and both Actions links belong
in [PR #30](https://github.com/SergeyRassohin/Forest-Keeper/pull/30), avoiding a
self-referential SHA in its own commit.

- [Runtime/restart evidence](stage8-runtime-2026-10-25.json) pins actual candidate and image IDs.
- [Production-profile evidence](stage8-production-2026-10-25.json) records all four smoke groups.
- [Performance evidence](stage8-performance-2026-10-25.json) includes distributions, outcomes,
  real row counts, query plans, integrity visibility statistics and process RSS.
- [Independent architecture/security/product review](stage8-independent-2026-10-25.md)
  records its own targeted execution and evidence verification.
- [Gallery manifest](../../../frontend/public/interface/manifest.json) pins actual served
  bundle hashes, capture-source commit/tree, images and all accessibility/responsive checks.
  Capture image identities are historical provenance; the subsequent frontend rebuild
  embeds the refreshed static gallery with identical application bundle hashes. Final frontend
  distribution image: `sha256:6750877bcc7b6c53f657c0e0a0e21bfe6ae1021f1e5d687544450c704219a97e`;
  actual HTTPS serving was checked against the exact manifest and every bundle digest.

Reproducible commands and manual expectations: [test scenario](../stage8-acceptance.md).
Private environments/credentials, cookie fixtures and machine-specific logs are not committed.

## Acceptance gates

| Gate | Result on the application candidate |
| --- | --- |
| `bash scripts/check.sh` | PASS: documentation/gallery integrity, Ruff, mypy70 application files,278 backend unit tests,64 frontend component tests, lint, production build and E2E/gallery typechecks |
| `bash scripts/check-sast.sh` | PASS: Python Bandit and TypeScript security ESLint |
| `bash scripts/check-secrets.sh` | PASS: Git history and tracked working tree, no leaks |
| `bash scripts/test-security-gates.sh` | PASS: deliberately unsafe shell/B602, eval and PAT fixtures rejected |
| `bash scripts/check-dependencies.sh` | PASS: pip-audit and npm audit, zero known vulnerabilities |
| `bash scripts/check-integration.sh` | PASS:553 integration tests,278 deselected,303.20s; Alembic0008 head;15 real HTTPS browser tests,1.1min |
| Real HTTPS gallery | PASS:31 scenes ×2 themes ×2 screenshot viewports =124 PNG;124 Axe checks with zero violations;310 responsive checks at1920/1440/1280/1024/390px |
| HTTPS restart/recovery | PASS: five real independent file pairs, human-confirmed receipt/history unchanged across two restarts, durable partial backfill recovery, explicit version activation, stale-reference refusal and independent manual save |
| PostgreSQL/Redis failure | PASS: sanitized PostgreSQL503 and recovery; Redis-down manual Decision and exact committed referenced retry; restored default production fail-closed/operator revoked |
| Production profile | PASS: two concurrent100MB uploads/checksums/temp cleanup; HTTPS/file secrets/non-root/read-only/resources; real RQ readiness→stale→restored; PostgreSQL/Redis persistence and no credential values in inspect/logs |
| Independent targeted execution | PASS:15 tests,29 deselected,62.04s on exact candidate; fresh artifact/visual verification recorded separately |
| GitHub push and PR Actions | Mandatory green on final delivery SHA; exact status/run links recorded in PR #30 before READY TO MERGE |

The full integration run uses a detached worktree of the exact candidate and separate
owned PostgreSQL/Redis/HTTPS project, isolated from restart/gallery workloads. No test
threshold was reduced. No schema migration was added; existing migration preservation
regressions remain in the full suite.

The real browser gallery drives five independent CSV/XML import→normalization→matching→
Conflict→human Decision histories, then a new-case recommendation with genuine precedent
navigation and current source/value, dark-theme return/reload, begin-review token refresh,
unsaved draft preservation across theme changes, explicit confirmation and actual Registry
receipt. A manual override and subsequent contradiction abstention are exercised. Scene29
now targets the actual filled Human Review form in all four light/dark desktop/mobile
captures; the independent reviewer inspected the replacement images. Shared theme checks
cover system preference before React, explicit local preference, unavailable storage,
accessible labels/state, visible keyboard focus and confirmation-dialog focus. Axe covers
contrast on all captured pages; independent visual inspection checks readable controls,
status, source evidence, modal and selected value in both themes. No universal manual
contrast certification beyond these tested states is claimed.

## Performance — unchanged p95<=1s,10 distinct sessions

350 real API requests, zero failures. Warm in-process ASGI with real PostgreSQL/Redis;
HTTPS correctness/restart is measured separately. Each series has50 requests/10 sessions.

| Actual Decision/vector rows | Stage7 p50 / p95 / max, seconds | Stage8 p50 / p95 / max, seconds | Stage8 outcomes |
| --- | --- | --- | --- |
| 5 genuine independent cases | Not a capacity baseline | .633445 / .858970 / .894241 |50 RECOMMENDED |
| 100 | .210127 / .249737 / .267509 | .399030 / .693262 / .901342 |50 ABSTAINED / EVIDENCE_WINDOW_EXCEEDED |
| 1,000 | .247555 / .474149 / .489177 | .430014 / .528532 / .593999 |50 ABSTAINED / EVIDENCE_WINDOW_EXCEEDED |
| 10,000 | .420742 / .618654 / .655545 | .537267 / .910828 / .956232 |50 ABSTAINED / EVIDENCE_WINDOW_EXCEEDED |

Capacity fixtures contain actual immutable Decisions/vectors but copied synthetic provenance;
they prove neither industrial semantics nor10k independent positive evidence. PostgreSQL/OS
caches are warm. Process peak RSS about166MiB is Python process memory, not total server/container
memory.100k, fully cold OS cache and industrial semantic quality remain unverified.

Earlier measurements that exceeded the unchanged1s gate remain failures. The final fix
reuses already validated features from the same snapshot and isolates the unchanged scoped
integrity predicate so the existing partial index is preferred even on fresh non-visible heap
pages. Ranking settings are restored before ranking; rollback restores the same connection.
The independent injected-failure regression verifies this restoration and recovery. Supplemental
forced fresh/bloated10k relallvisible0 runs on the same application code produced Stage8
p95=.780239/.756529s; no integrity filter, rate limit, deadline or acceptance target was removed.

## Stage7 carry-over register — all14 dispositions

Owners below identify the responsible workstream; they do not imply implementation
of deferred systems. Owner approved these boundaries with the Stage8 policy proposal.

| # | Disposition | Owner and acceptance criterion | Stage8 evidence / retained blocker |
| --- | --- | --- | --- |
| 1 production embeddings | BLOCK_PRODUCTION_RECOMMENDATION | Stage9 implementer + product owner: accepted real provider, versioned artifacts, industrial semantic validation/offline installation | Production flags fail-closed regression; synthetic demo clearly labelled. No positive production claim |
| 2 capacity100k | DEFER_WITH_OWNER_AND_ACCEPTANCE | Performance owner + product owner: separately measured100k actual rows, realistic distributions,10sessions | Stage8 harness measures100/1k/10k only;100k remains unverified |
| 3 diversity/independence | RESOLVE_STAGE8 | Stage8 implementer/reviewer: real separate imports vs clones/transitive current correlation | Unit graph boundaries; real5 independent / repeated imports /5:1 integration and browser fixtures; capacity clones are explicitly synthetic |
| 4 cold proof | DEFER_WITH_OWNER_AND_ACCEPTANCE | Performance owner: controlled OS+DB cold profile before fully-cold claims | Report warm profile and retained OS cache; restart proves persistence, not fully-cold performance |
| 5 unit/family compatibility | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product/domain owner: approved dimension/family mapping and regression fixtures | Exact canonical domain/entity/attribute/type/unit retained; no inference or expansion |
| 6 legacy source roles | RESOLVE_STAGE8 | Operator + Stage8 reviewer: explicit scoped versioned actual source identities/types/profile hashes | Missing/ambiguous/wrong type/new mapping tests; unknown correspondence abstains |
| 7 Rule/Template/authority/Codex | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product/domain owner + future #17 implementer: active scoped versioned configuration and precedence acceptance | NOT_CONFIGURED/NOT_DEFINED; apparent unsupported authority abstains; no shadow rules |
| 8 confidence/calibration | RESOLVE_STAGE8 | Product owner/reviewer: approved deterministic evidence measure, adversarial cases | Versioned group-count policy,0/1/4/5/20/21 boundaries; no probability or cosine confidence |
| 9 races/revocation/cache | RESOLVE_STAGE8 | Stage8 implementer/security reviewer: coherent snapshot + atomic referenced save | Real201/409 two-reviewer, reopen barrier, scope-revoke barrier, version stale, persistent retries; [runtime PASS](stage8-runtime-2026-10-25.json) |
| 10 integrity/coverage | RESOLVE_STAGE8 | Stage8 implementer/security reviewer: no partial positive on corrupt/unknown compatible evidence | Actual lineage projections, corrupt receipt/vector regressions; compatible skip blocks, incompatible skip does not |
| 11 timeout/load | RESOLVE_STAGE8 | Stage8 implementer/performance reviewer: shared120/min, total protective1500ms, NFR p95<=1s at10sessions | Per-SQL remaining deadline/gate release/pool reset and shared-rate tests; [performance PASS](stage8-performance-2026-10-25.json) |
| 12 documentation drift | RESOLVE_STAGE8 | Stage8 implementer/reviewer: actual main/PR status, explicit new numbering and runtime contract | README/progress/architecture/API/model/lifecycles/current contract updated; historical records preserved |
| 13 external vertical | DEFER_WITH_OWNER_AND_ACCEPTANCE | External reviewer + product owner, #18/#20: independent own-file fresh install through full accepted MVP | Stage8 own-file HTTPS demo supports deterministic segment; Qwen/provider/external MVP acceptance remain open |
| 14 license/update/offline supply | DEFER_WITH_OWNER_AND_ACCEPTANCE | Product + deployment/security workstream: separate signed/versioned supply and installer acceptance | Existing trust boundaries preserved; no new license/update claims or scope expansion |

## Remaining approval boundary

Do not merge automatically or close #17/#18/#20. Final CI must match the final branch
HEAD for both push and PR. Once local acceptance, independent final review and CI pass,
mark READY TO MERGE and leave the merge decision to the owner.
