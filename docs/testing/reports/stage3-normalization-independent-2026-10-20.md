# Independent Stage 3 review — 2026-10-20

Runtime SHA: c685ed71558374fde4adfe9fde525849b56ce94a (feat/stage3-normalization). Application sources were not edited.

## Personally executed

- `FK_TEST_INTEGRATION=1 uv run --frozen pytest tests/test_normalization.py tests/test_normalization_integration.py -q`: **106 PASS** (68 unit +38 integration), 13.79s. Host configuration sourced privately from /tmp/fk-stage3-dev.env. Fixtures used disposable database schema and namespaced queues, and completed cleanup.
- Includes exact expected values across CSV/XLSX/generic XML/1C XML; raw/provenance preservation and append-only rejection; date/decimal/unit edge cases; missing/null/empty distinction; seeded Unicode/numeric properties; immutable snapshots/version history; distinct entities for distinct raw records; real RQ and duplicate delivery; atomic checkpoint retry/resume; lost jobs/late enqueue; six concurrent API starts; RBAC and mandatory Origin; migration down/up preserving Stage2 raw.
- Retested former trim=False finding through all four independent trim/collapse combinations: PASS.
- Retested former startup-only recovery finding using actual idle RQ dequeue maintenance after fresh NEW skip and stale age: queued and completed, PASS.

## Read-only review

Reviewed normalization profiles, numeric/date/string functions, pipeline, jobs/recovery, models, API routes, migration0004, worker integration, and normalization browser code/tests. The snapshot stores complete declarative rules, hash and engine version; EntityValue retains original source value and raw-record provenance. Deterministic identity includes raw UUID and mapping fingerprint, avoiding cross-source matching. Immutable run origin/output triggers preserve historical interpretation. UI explicitly states normalization does not establish truth; no matching/conflict/decision or other Stage4 work was introduced. The NULL canonical status and technical pre-match representation are explicitly documented in the decision log rather than introducing new enum states.

Reviewed installed RQ idle dequeue loop: repeated maintenance hook invokes ForestWorker recovery after dequeue timeout, resolving the original quick-restart gap. Recovery retains advisory locks and fresh row reads. Both earlier findings are closed; **no remaining reproducible findings** within this reviewed scope.

## Limitations

This artifact confirms backend tests, source review and the Stage3 browser retest below. Full security gates, CI, 100k capacity and production harness are executed separately by the parent and are not claimed here as independently executed. Two emitted test warnings (Starlette TestClient deprecation and Pydantic alias metadata) did not cause failures.

## Independent browser retest

HEAD 127a45d4fb8769f80209c301a6f3caa878797ec7; runtime remains c685ed7, subsequent changes are test/docs. Personally ran `FK_E2E_BASE_URL=https://localhost:18443 FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e -- normalization.spec.ts` against the isolated fk-stage3 environment: **1 PASS**, 16.2s (scenario 15.2s). Prepared owned temporary E2E accounts using tests.e2e_accounts and cleaned them in an EXIT trap with the same private environment; deploy/local/e2e.json absence verified afterward.

Real Chromium verified CSV and 1C XML uploads followed by normalization; all three reference mass spellings render raw unchanged and normalized 12.5 kg VALID, conversion rules/factors and source/hash/position visible; unknown-unit and invalid-date explanations visible; raw API payload unchanged; UI states normalization does not establish truth; entity sets remain disjoint across sources; VIEWER sees completed results but cannot start normalization. No additional findings. Both former findings remain closed.

Final independent result: **106 backend checks +1 Stage3 browser scenario PASS; no open reproducible findings in reviewed scope.** No application source or GitHub mutations.

## Follow-up: independent lifecycle oracle

Read the final test-only diff replacing production TRANSITIONS as the expected oracle with five explicitly listed edges. Compared these against Object Lifecycles v0.1, AnalysisRun diagram (lines92–97): NEW→QUEUED, QUEUED→PROCESSING/FAILED, PROCESSING→COMPLETED/FAILED. The test now checks all25 source/target pairs against an independent contract; no application runtime change. Personally reran the entire normalization unit module: **68 PASS in0.53s**, including all25 lifecycle pairs. No findings; prior106 backend +1 browser result remains applicable to unchanged runtime c685ed7.
