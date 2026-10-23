# Stage 6: Human Review + Decision Registry — acceptance

23 октября 2026, Europe/Moscow. Требования: [issue #25](https://github.com/SergeyRassohin/Forest-Keeper/issues/25). Ветка `codex/stage6-human-review`, merge base `04793d9e3c00a73399388544d76f09a2758b45e1` (принятый Stage 5.1, PR #24). Основная реализация сохранена в `d4b9a55`, checkpoint отправлен как `556c0cb`; существующие коммиты не переписывались.

Этот отчёт фиксирует реализацию и локальные/независимые доказательства. **READY TO MERGE требует также успешного CI точного итогового HEAD; SHA и ссылки на оба final-head запуска фиксируются в PR.** CI `556c0cb` [39939784871](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39939784871) завершился FAIL на устаревшей галерее. Причина устранена настоящей пересъёмкой текущего приложения; проверка актуальности не отключалась. Статус этого исторического CI не подменяется зелёным.

Merge и принятие Stage 6 в main требуют отдельного разрешения владельца и успешного CI точного merge commit. #25/#18/#20 автоматически не закрываются. Stage 7 не начат.

## Реализованный результат и граница

Реальный путь: CSV + XML → сохранённые SourceSystem/Import/Raw → нормализация → matching → persisted Conflict → явный Human Review → отдельный immutable Decision → audit/history → restart → тот же Decision. Пользователь видит evidence перед действием, подтверждает итог и получает server-confirmed receipt. Источники, RawRecord, EntityValue и Conflict Basis не переписываются.

Модульный монолит сохранён: `app/decisions`, существующий PostgreSQL и Web Client через HTTPS cookie + Origin. Similar Decision Retrieval, embeddings, Recommendation Engine, AI/LLM inference, RuleSuggestion, автоматическое изменение Forest Codex/Gold Reference, Publisher и write-back не реализованы. Модели не загружались. Нет нового native/desktop клиента, ролей или permissions.

Архитектурный entry gate и разрешение расхождений: [entry gate](stage6-entry-gate-2026-10-23.md), [Decision Log](../../decisions/decision-log.md), [Human Review](../../development/human-review.md), [Registry/API/recovery](../../development/decision-registry.md). Более поздний issue #25 объединяет прежние плановые этапы Human Review/Registry в Stage 6 и исключает рекомендации из текущей итерации.

| Canonical DecisionType | Состояние Conflict | Гарантия |
| --- | --- | --- |
| SELECT_VALUE | RESOLVED | Source/value reference входит в frozen evidence, VALID/PRESENT |
| ENTER_VALUE | RESOLVED | Однозначные frozen kind/unit, canonical validation, input + conversion trace |
| INSUFFICIENT_DATA | INSUFFICIENT_DATA | Значение не выдумывается, selected_value = null |
| DEFERRED | IN_REVIEW | Рассмотрение остаётся незавершённым, selected_value = null |

GET не меняет lifecycle. Отдельный review POST переводит OPEN в IN_REVIEW. Явный пересмотр с permission decision.supersede сохраняет прежний head до новой атомарной записи. Старые факты остаются; ACTIVE/SUPERSEDED выводятся из immutable successor relation. Новая загрузка создаёт новый случай, не переоткрывает старый молча.

## Данные, авторизация, транзакция

Decision хранит UUID, case/entity/domain/attribute/business key, серверного actor ID/имя/roles snapshot, UTC timestamp, outcome/value/type/unit/source/value references, reason, historical evidence/profile/config context, schema version, review token/hash, persistent key/request hash, predecessor и audit linkage. PATCH/DELETE отсутствуют; DB UPDATE/DELETE запрещены. Unique root/successor и same-case predecessor FK исключают ветвление; predecessor обязан уже существовать, циклы не создаются. Conflict разрешает только lifecycle/version/head updates; evidence защищён.

User.data_domains дополняет существующую XLSX action matrix. Новый пользователь имеет [] и не получает доступ к Conflict/Decision; wildcard выдаётся явно. Миграция сохраняет прежний глобальный доступ старых аккаунтов как ['*']. ADMIN сам по себе не принимает business Decisions; VIEWER только читает. Назначение scope требует user.manage + role.assign, свежую аутентификацию и аудит. Scope/permissions проверяются сервером на каждом запросе, включая replay receipt. Это не полная переделка legacy ingestion API в multitenant isolation.

Row lock Conflict + context token + уникальная lineage дают один head. Actor + Conflict + UUID key + одинаковый payload возвращает прежний ID; другой payload — 409. Ключ хранится вместе с Decision, не в Redis. Проверка успешного replay выполняется до stale token, после текущей авторизации/scope. Decision/head/lifecycle/business audit коммитятся атомарно. Ошибка до commit откатывает всё; потерянный ответ после commit восстанавливается повтором прежнего запроса.

Валидация покрывает оба источника, forged IDs/actor/status, unknown/invalid/missing, ambiguous kind/unit, Unicode, decimal comma/precision/exponent, даты, пустые/oversized reason/value и hostile text. Числовые business ranges не выдумываются. React отображает текст, не исполняет HTML. Audit/ошибки не выводят credentials, raw payload, reason/corrected value или SQL parameters в технические ответы/логи.

## Проверки

| Gate | Результат |
| --- | --- |
| `bash scripts/check.sh` | PASS: doc links, галерея, 6 model-tool tests, ruff/format/mypy, 234 backend unit, 43 frontend component, build, E2E typecheck |
| `bash scripts/check-integration.sh` | PASS: 469 реальных backend integration, migration head, 13 HTTPS browser E2E |
| `bash scripts/check-sast.sh` | PASS: Bandit app/migrations + ESLint security |
| `bash scripts/check-secrets.sh` | PASS: Gitleaks Git history + tracked worktree, redacted |
| `bash scripts/test-security-gates.sh` | PASS: scanners отвергли shell injection/eval/PAT fixtures |
| `bash scripts/check-dependencies.sh` | PASS: pip-audit + npm audit, известных уязвимостей не обнаружено |
| production smoke | PASS: два одновременных 100 MB HTTPS upload с exact checksums; file secrets; non-root/read-only/resources; реальный RQ job; worker stale/stopped/recovery; PG/Redis/files persistence; нет credentials в inspect/logs |
| независимое review/retest | См. [independent report](stage6-human-review-independent-2026-10-23.md); блокирующие findings исправлены и перепроверены |

Backend: 703 теста (234 unit + 469 integration); frontend: 43; browser: 13. Отдельно 6 проверок model tooling и 23 Axe/115 viewport checks. Оставшиеся предупреждения Starlette/httpx и Pydantic alias относятся к существующим зависимостям/старым fixtures; failures нет.

Новые Stage 6 tests находятся в `test_decision_validation.py`, `test_decisions_integration.py`, `test_decision_migration.py`, `HumanReview.test.tsx`, `Decisions.test.tsx`, `tests/e2e/decisions.spec.ts`. Регрессия предыдущих стадий выполнена общими gates. Проверялись оба business role, VIEWER/ADMIN/no-role, scope и role revocation, Origin, duplicate/change-key/stale/head/concurrent/retry, audit failure, failure after insert и committed-response loss. Отдельная fault injection блокирует optional outbound socket creation и Redis ping; review продолжает работать. Это проверка отсутствия optional dependency, не заявление о сетевой изоляции всей машины.

0007 migration: upgrade/repeat, empty downgrade/upgrade, populated Stage 5 Conflict/evidence + legacy account preservation, отсутствие fake Decision backfill, transactional DDL interruption rollback и повторный upgrade. При наличии Decision история не удаляется: downgrade отказывается выполнять destructive rollback.

## Реальный restart и concurrency

[Machine-readable restart proof](stage6-restart-2026-10-23.json), harness `backend/tests/restart_decisions.py`. Он требует явные project/env/override/HTTPS URL и совпадение PG port с выбранным проектом; default/production stack не используется. Собственные runtime accounts по завершении отключаются и сессии отзываются; business facts и volumes сохраняются.

- Conflict `46669941-e4c6-5c3c-9a63-bf2b3142fc4c`.
- Decision `624a7b7d-d1cb-40a7-b972-897265cd8d31`, superseding Decision `485ed5be-d571-4b8c-9050-63d914121bd1`.
- Два разных reviewer accounts отправили реальные HTTPS запросы с одним token/head: результат 201/409 и один effective head. Дополнительно две браузерные reviewer-сессии проверили UI stale/error path.
- Сохранение Decision работало при остановленных worker/Redis; readiness честно показывал Redis unavailable.
- После перезапуска PostgreSQL/Redis/backend/frontend и восстановления worker совпали полные HTTP карточки, история из трёх записей и hashes Decision/raw/original metadata/normalization/matching/evidence.
- Повтор исходного key после superseding и restart вернул первоначальный ID/SUPERSEDED; replay второго key вернул второй ID.
- Независимый REVIEWER отдельно выполнил browser logout/login после реального restart и увидел прежний ID/полное содержимое в Registry.

## Производительность и реальные экраны

[Capacity measurements](stage6-capacity-2026-10-23.json): собственная временная schema, real CSV/XML evidence seed и API Decision; синтетические queue copies для 100/1k/10k/100k Conflict; 10 authenticated sessions, по 30 измерений каждого из пяти endpoints. Это read-capacity queue test, не повторный полный импорт 100k и не benchmark 100k Decisions. Registry/history содержат один Decision; ограничение явно сохранено в результатах. Decision-create latency измеряется без придуманного SLA. Metadata baseline p95≤1s/10 sessions проверяется по опубликованным endpoint measurements; Conflict detail baseline≤2s не расширяется на AI.

| Conflict queue | Queue list p95 | Review context p95 | Decision list p95 | Decision detail p95 | History p95 |
| --- | --- | --- | --- | --- | --- |
| 100 | 0.4406s | 0.2589s | 0.1345s | 0.1406s | 0.1085s |
| 1000 | 0.6668s | 0.2733s | 0.1360s | 0.1129s | 0.1224s |
| 10000 | 0.4452s | 0.2751s | 0.1829s | 0.4582s | 0.4477s |
| 100000 | 0.5210s | 0.6660s | 0.5696s | 0.1370s | 0.1310s |

Observed API Decision create: **0.0268s**, без утверждённого отдельного SLA. Benchmark process peak RSS: **179.05 MiB**.

Среда: managed Linux/Docker vfs, quota 4 CPU, memory limit 32 GiB; Python 3.13.16, Node 24.19.0, PostgreSQL 17/pgvector, Redis 7.4. Process peak RSS относится к benchmark process, не ко всему серверу. В JSON сохранены source revision и query plans; для большой queue PostgreSQL использует backward index-only scan по ix_conflicts_created. Seq scan маленького Registry из одной записи не выдаётся за large-registry performance proof.

[Галерея](../../../frontend/public/interface/index.html), [manifest](../../../frontend/public/interface/manifest.json): 23 настоящих HTTPS screenshots, 23 Axe scans без нарушений WCAG A/AA, 115 проверок 1920/1440/1280/1024/390 px без body overflow. Stage 6: 19-human-review, 20-decision-confirmation, 21-decision-receipt, 22-decision-registry, 23-decision-history. Кнопка истории исправлена по Axe; выбранное значение и reason согласованы после независимого visual finding. Source tree и served bundle hashes проверены; изображения не рисовались и не ретушировались. Новая внешняя публикация сайта этим отчётом не заявляется.

## Заключение stage gate

Соответствие product intent/архитектуре/canonical model/lifecycles/RBAC/human-in-the-loop проверено отдельно от тестов. Conflict не подменён Decision; canonical representation/UNKNOWN не объявлены истиной; новая память хранится структурированно в PostgreSQL; авторизация и audit остаются server-side; история не переинтерпретируется новой конфигурацией. Forest Codex/Gold Reference и source data не изменяются. Следующий этап и AI не протащены в текущий workflow.

Известные ограничения: explicit domain scope не является retrofit всех legacy ingestion endpoints; offset pagination не даёт snapshot cursor при конкурентных вставках; hashes не являются электронной подписью против DB superuser; history-preserving downgrade требует отдельного проверенного backup/recovery плана; capacity не доказывает 100k-row Registry/history; полный MVP #18/#20 остаётся незавершённым из-за Stage 7+.

Local/runtime/security/independent acceptance позволяет предъявить Stage 6 владельцу. Окончательное **READY TO MERGE** фиксируется в PR только после зелёного CI exact final HEAD. Автоматический merge запрещён.
