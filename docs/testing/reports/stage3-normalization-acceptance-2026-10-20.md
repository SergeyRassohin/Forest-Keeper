# Stage 3 normalization — проверка 20.10.2026

Спецификация: [issue #12](https://github.com/SergeyRassohin/Forest-Keeper/issues/12). Реализация и финальный HEAD/CI: [PR #13](https://github.com/SergeyRassohin/Forest-Keeper/pull/13), [checks](https://github.com/SergeyRassohin/Forest-Keeper/pull/13/checks). Принят после merge `6a494534a49960b79fdf64e5e2b8436c32011688` и [зелёного main CI](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39452965438); issue #12 закрыт. Измерения ниже относятся к исходным указанным SHA.

Runtime и capacity: `c685ed71558374fde4adfe9fde525849b56ce94a`. Полные проверки и независимый browser retest: `127a45d4fb8769f80209c301a6f3caa878797ec7` (после runtime изменены только selector E2E и CSV fixture). Позднее ожидаемые lifecycle transitions в тесте отделены от production-константы; все 68 unit повторены автором и независимым проверяющим. Runtime не менялся. Финальный SHA и ссылка на соответствующий GitHub Actions run фиксируются в описании PR после коммита отчёта.

## Результат

Локальный набор: **543 PASS, 0 FAIL, 0 SKIP**: 163 backend unit, 355 backend integration, 17 frontend и 8 real Chromium HTTPS E2E. В раздельных pytest-профилях противоположная категория deselected, а не skipped. Из backend-проверок 68 unit и 38 integration добавлены для нормализации.

- `scripts/check.sh`: PASS — Ruff, форматирование, mypy, pytest, frontend lint/tests/build и TypeScript E2E.
- `scripts/check-integration.sh`: PASS — реальные PostgreSQL/Redis, RQ, миграции, browser.
- `scripts/check-sast.sh`: PASS — Bandit и TypeScript security ESLint.
- `scripts/check-secrets.sh`: PASS — история Git и tracked contents, Gitleaks.
- `scripts/test-security-gates.sh`: PASS — отрицательные shell injection/eval/PAT fixtures отклонены.
- `scripts/check-dependencies.sh`: PASS — pip-audit/npm audit, известных уязвимостей не обнаружено.
- Production smoke на пересобранных Stage3 backend/frontend images: PASS — две одновременные загрузки по 100 MB с проверкой checksum/cleanup, секреты из файлов, HTTPS, non-root/read-only/resources, реальное задание RQ, stale/stopped/restored worker, persistence PostgreSQL/Redis/original storage и отсутствие credentials в логах/inspect.

## Миграции, сохранность, восстановление

`0003_imports → 0004_normalization`: PASS. На собственном fixture проверены повторный upgrade, downgrade к 0003 и повторный upgrade: данные импорта/raw сохранились. Миграция не делает destructive backfill. Downgrade удаляет результаты нормализации и не является безусловным production rollback.

На отдельном Stage3 контуре дополнительно пересозданы API и worker из последних образов: сохранённый COMPLETED запуск и все пять его записей до/после совпали, включая provenance, версии правил, raw и normalized. SHA-256 сериализованного снимка `b7232cef454e9582f1a5e83b508ec38e3e4b2d86547e2a244555875166c7a4e0`. PostgreSQL в этом сценарии не останавливался; его restart/persistence отдельно подтверждён production harness.

Интеграционные проверки охватывают CSV/XLSX/generic XML/1C XML, заранее сохранённые expected.json, raw immutability и append-only outputs, provenance, version history, повторные и параллельные доставки, шесть конкурентных POST, локальные ошибки атрибутов, атомарный checkpoint после 100 записей, новый retry и продолжение PROCESSING после hard-stop. Отдельная регрессия проверяет periodic RQ maintenance: свежий NEW пропускается, позднее idle worker публикует его без POST пользователя. Проверены RBAC и обязательный Origin по существующей матрице.

## Браузер и независимое ревью

Полный набор 8 E2E: PASS. Новый сценарий загружает CSV и синтетический 1C XML, нормализует оба источника, проверяет дословные raw значения трёх масс и общий результат `12.5 kg`, source/position/checksum, mapping/conversion evidence, INVALID/UNKNOWN и VIEWER без кнопки запуска. Canonical IDs двух источников различны; matching отсутствует.

[Независимый отчёт](stage3-normalization-independent-2026-10-20.md): лично повторены **106 backend + 1 browser PASS**, открытых замечаний нет. Закрыты два найденных дефекта: collapse_whitespace скрыто выполнял trim; восстановление NEW зависело от старта worker/нового POST. Исправления проверены отдельными регрессиями и повторным независимым прогоном. Проверяющий не менял код.

## Capacity

**PASS** для всех четырёх размеров. [Машиночитаемые измерения](stage3-normalization-capacity-2026-10-20.json), runtime `c685ed7`, clean tree на старте. По два source dataset на каждый размер, по 30 атрибутов, реальные API/PG/Redis/RQ; SimpleWorker выполняет тот же pipeline. Проверяется фактическое число EntityValue в БД, а не только счётчик запуска.

| Записей в каждом из 2 источников | Всего значений | Импорт, с | Нормализация, с | Metadata p95, с / 10 сессий | Peak RSS процесса, MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 6 000 | 0.434 | 0.549 | 0.3112 | 161.25 |
| 1 000 | 60 000 | 0.837 | 5.396 | 0.2989 | 177.22 |
| 10 000 | 600 000 | 5.445 | 49.199 | 0.2580 | 188.23 |
| 100 000 | 6 000 000 | 60.353 | 519.759 | 0.2145 | 243.41 |

Все значения VALID; failures/warnings — 0. В самом большом профиле два файла по 30000381 байт; processing time указан для обоих источников вместе. Metadata — GET detail завершённого AnalysisRun, 100 запросов из 10 параллельных сессий, предел 1 секунда соблюдён. Измерение не утверждает p95 всех продуктовых операций. Peak RSS включает импорт, нормализацию и чтение в одном процессе; это не память всей PostgreSQL/Redis инфраструктуры.

Стенд: Linux x86_64, Python 3.13.16, PostgreSQL17/pgvector, Redis7.4, cgroup quota4 CPU/32GiB. Ресурсы общие с другими acceptance-проверками, данные изолированы; время не является production SLA. После каждого размера удалены собственные schema, очередь, rate-limit keys и временные файлы. Команда из backend: `FK_TEST_INTEGRATION=1 uv run python -m tests.benchmark_normalization --records 100 1000 10000 100000` с конфигурацией disposable development PG/Redis.

Локальная приёмка и независимое ревью: PASS. Финальный статус READY TO MERGE вместе с точным HEAD и зелёным GitHub Actions публикуется в описании PR; после изменения HEAD CI проверяется заново.

## Ограничения

- Первый реальный pilot domain и реальная выгрузка 1C остаются открытыми решениями; Material и capacity профили синтетические, конфигурационные, не бизнес-логика заказчика.
- CanonicalEntity — pre-match представление одного RawRecord на версию правил; status=NULL, без придуманного workflow. Нормализация не определяет истину и не объединяет источники.
- Профили версионируются в Git; редактор пользовательских mappings и CustomerTemplate workflow не входят в этап.
- Decimal имеет документированные границы (38 цифр, exponent/adjusted ±18); единицы и форматы дат перечислены явно. XLSX decoded float даёт WARNING; неизвестные/неоднозначные значения не угадываются.
- Recovery имеет защитное окно 60 секунд; maintenance 30 секунд, idle dequeue до 105 секунд; занятый единственный worker проверяет потерянные задания после текущего job. Повтор FAILED создаёт новый запуск.
- Производительность нормализации измеряется отдельно от matching/AI/полного MVP. Этап 4 не начат.

## Architecture / Product Intent Gate

Дополнительная проверка новых требований от 20.10.2026 перед этапом 4: [gate](stage4-entry-gate-2026-10-20.md). PASS: продукт остаётся read-only надстройкой, raw/provenance неизменяемы, canonical не объявляется истиной, AI и автоматического изменения критериев нет. Mapping snapshots и engine/hash сохраняются; новые версии не переинтерпретируют историю. Gold Reference/CustomerTemplate ещё не реализованы и не подменяются synthetic normalization profile. Lineage позволяет будущие impact lookup и явный новый run; полный activation/rollback/stale workflow относится к этапам 11–12. Устаревший pre-merge статус документации исправлен без изменения исторических результатов тестирования.
