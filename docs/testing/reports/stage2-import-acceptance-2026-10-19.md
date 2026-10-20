# Этап 2: источники и импорт — отчёт 19.10.2026

**Дополнение после нового ревью:** на `ddcebca` найдены ещё четыре дефекта. Их исправления, регрессии и актуальный CI описаны в [отчёте закрытия замечаний](stage2-import-review-fixes-2026-10-19.md). Числа и SHA ниже относятся к первоначальной реализации `6380d5c` и сохранены как история проверок.

Реализация [ТЗ #7](https://github.com/SergeyRassohin/Forest-Keeper/issues/7) в [PR #8](https://github.com/SergeyRassohin/Forest-Keeper/pull/8). Этап готов к ревью; принятие и merge выполняются отдельно.

## Версия и среда

Runtime/test commit: **6380d5cea126be96ee2a5b2f207dbae4c7c243c0**, ветка `feat/stage2-import`; base main **4efa434a4ee794d127bdd3b4e82f5afb19be16d3**. Последующие изменения отчёта не меняют runtime. Локально пройдены все шесть обязательных gates: **393 теста, 0 failed**. Exact-SHA GitHub Actions [push run](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39315287655) — **SUCCESS**. Дополнительный [PR run](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39315316916) для того же runtime SHA — **SUCCESS**. Перед merge также проверяется CI актуального HEAD PR, включающего этот отчёт.

Cloud Linux, Python 3.13.16, Node 24.19.0, PostgreSQL 17/pgvector, Redis 7.4/RQ, Docker Compose и системный Chromium. CI использует Node 22 и собственный Chromium Playwright. Integration работает с отдельными PostgreSQL schemas, файловыми каталогами и очередями. Синтетические browser-пакеты/raw/audit сохраняются как история в development БД; временные аккаунты удалены. Чужие данные/volumes не удалялись.

## Тесты и gates

| Проверка | Результат |
|---|---|
| `bash scripts/check.sh` | PASS: ruff/format/mypy, **74 backend unit**, **11 frontend**, ESLint, TypeScript/E2E types, production build |
| `bash scripts/check-integration.sh` | PASS: **301 integration/API**, актуальная миграция, **7 HTTPS browser E2E** |
| `bash scripts/check-sast.sh` | PASS: Bandit и TypeScript security ESLint, 0 issues |
| `bash scripts/check-secrets.sh` | PASS: история Git и tracked tree, 0 findings |
| `bash scripts/test-security-gates.sh` | PASS: три отрицательных scanner fixtures отклонены |
| `bash scripts/check-dependencies.sh` | PASS: pip-audit/npm audit, 0 известных уязвимостей |

Из 375 backend-тестов **145 новых** относятся к Stage 2: 66 parser/storage/lifecycle unit и 79 integration/API. Source/import RBAC проверяет 10 операций × 5 role-наборов по canonical XLSX, включая отсутствие ролей. Штатные auth-тесты остаются зелёными. Один upstream warning Starlette о будущем переходе TestClient с httpx на httpx2 не влияет на результат; ошибок тестов нет.

Полные короткие логи gates, capacity и миграций: [каталог evidence](stage2-import-2026-10-19/); [числа, hashes и результаты](stage2-import-2026-10-19/evidence.json). Пробел в конце строки CSV-fixtures намеренный: тест проверяет сохранение исходного значения `" 2.00 "`.

## Definition of Done из issue #7

| № | Результат и доказательство |
|---|---|
| 1 | PASS: миграция 0003 создаёт SourceSystem, ImportBatch, RawRecord и technical ImportErrorRecord; downgrade/upgrade/repeated upgrade проверены в отдельной schema, auth-таблицы и контрольная запись сохранились. |
| 2 | PASS: оригинал сохраняется эксклюзивно под UUID, fsync/read-only; checksum сверяется по сохранённым байтам. Runtime restart backend/worker/frontend/PostgreSQL/Redis сохранил SHA-256 и raw/provenance fingerprint. |
| 3 | PASS: duplicate в пределах source+SHA-256 возвращает 200/тот же batch. Четыре конкурентные загрузки дают один новый batch/original и три duplicate; другой источник получает самостоятельный provenance. |
| 4 | PASS: fixtures CSV, первый worksheet XLSX, generic XML и тестовый 1С XML дают ожидаемые raw/errors/status из manifest. Ведущие нули, пробелы, многострочные значения и formula text сохранены. |
| 5 | PASS: загрузка возвращает статус до parsing; реальная Redis/RQ-задача создаёт raw. Повтор исполнения не дублирует позиции; PROCESSING replay сохраняет ID ранее записанных raw. |
| 6 | PASS: CSV даёт 2 raw + 2 errors; XML — 2 + 1. NUL/слишком длинный XML type становятся ошибкой одной записи. Сбой после chunk сохраняет первые 500 raw; retry создаёт новый batch. |
| 7 | PASS: UPDATE/DELETE RawRecord запрещены DB-trigger; original metadata также неизменяема. Payload, source_position и batch→source→original/checksum восстанавливают происхождение. |
| 8 | PASS: backend проверяет каждую source/import permission по XLSX. Нет auth/разрешённого Origin — отказ; Authorization не даёт альтернативного входа. |
| 9 | PASS: реальный Chromium через HTTPS создаёт два источника и загружает CSV + 1С XML. |
| 10 | PASS: оба пакета видны в браузерном списке со статусом и metadata. |
| 11 | PASS: карточка показывает исходные записи, checksum, uploader/time и source_position; frontend экранирует текст payload. |
| 12 | PASS: повтор CSV в браузере показывает сообщение о дубликате и открывает тот же batch; partial fixture показывает ошибки и пригодные raw. |
| 13 | PASS: локальные tests/gates и exact-runtime-SHA CI; перед merge проверить также актуальный documentation HEAD PR. |
| 14 | PASS: нормализация, matching, conflicts, decisions и AI не реализованы в этом PR. |

## Capacity

Opt-in `tests.benchmark_import --records 100000` выполнен повторно на указанном runtime SHA после фиксации кода. Два разных источника, каждый **100000 записей × 30 атрибутов, 30000381 байт**, прошли upload API → реальный RQ → RawRecord со статусом COMPLETED за **19.911 и 21.638 секунды**. Проверены количество raw и 30 полей записи.

Затем 10 одновременных пользовательских сессий выполнили 100 metadata-запросов: **p95 = 0.2475 с**, baseline ≤1 с выполнен. Это ASGI/TestClient-профиль с реальными PostgreSQL/Redis/RQ, без сетевой задержки gateway. Отдельные browser E2E проверяют HTTPS-путь; эти цифры не объявляются production SLA. Проверенный размер dataset около 30 MB; upload-limit настроен на 100000000 байт, boundary/streaming overflow проверяются отдельно. Benchmark не входит в быстрые unit tests и удаляет только собственные данные.

## Независимое ревью

Отдельный агент `/root/independent_review`, не писавший runtime, выполнил read-only review и собственные API/DB/XML/XLSX probes, 66 unit и 56 целевых RBAC/immutability tests. **Открытых findings нет.** [Отчёт](stage2-import-2026-10-19/independent-review.md) сохраняет первоначальные дефекты и их независимые retests; [fingerprints](stage2-import-2026-10-19/independent-snapshot.json) совпадают с runtime-файлами указанного commit.

Закрыты: recovery race с уже завершившимся worker, окно stale NEW до enqueue, потеря хороших строк из-за NUL/длинного XML type, XLSX sparse-row workload и обходы через OOXML relationships, ложный технический IMPORT_FAILED после позднего callback. Worker/recovery используют общий advisory lock и свежий DB-read. Финальный XLSX preflight проверяет именно листы, на которые ссылается workbook; опасные tiny fixtures отвергнуты примерно за 0.1–0.15 с, обычный workbook читает 2 записи.

Первый browser-run обнаружил ошибку exact-label locator нового теста для select. Исправлен тестовый locator на доступную роль combobox; последующие отдельный и полный прогоны — 7/7 PASS. Это не скрывается как первоначально успешный прогон.

## Уточнения контракта и ограничения

- Canonical SourceSystem не перечисляет полный source_type enum. Минимальные FILE/ONE_C, duplicate 200, async acceptance 201, GET raw и retry новым batch явно зафиксированы в API/decision log. Новых lifecycle-состояний, ролей или неявных ADMIN business permissions нет.
- 1С — минимальный синтетический XML-профиль, требующий сверки с реальной пилотной выгрузкой. Namespace/произвольные production-форматы не заявлены. CSV UTF-8 с запятой; XLSX — первый data worksheet.
- UI выбирает первые 100 источников; списки пакетов/raw/errors листаются по 50. Parser/storage limits описаны в [Import subsystem](../../development/import.md), включая ZIP expansion, координаты XLSX, XML depth и 1 MB на raw record. Выход за пределы даёт ошибку, без silent truncation.
- FS и DB не имеют общей транзакции: crash до регистрации batch может оставить невостребованный UUID-файл. Автоудаления оригиналов нет. После регистрации stale NEW восстанавливается; прерванные задачи становятся FAILED и допускают явный retry. Распознавание hard kill зависит от RQ maintenance/timeout.
- Файловые mode/DB triggers защищают обычный runtime/API, не заменяя backup и административные права владельца инфраструктуры. Перед промышленным пилотом нужен отдельный pentest по testing strategy. Этот отчёт покрывает Этап 2.
