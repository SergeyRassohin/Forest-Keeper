# Conflict Engine — Stage 5

Реализация в отдельной ветке/PR по [ТЗ #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21).
До merge и приёмки это не описание принятого main. Conflict фиксирует проблему;
MatchCandidate фиксирует идентичность; Decision будет отдельным человеческим бизнес-фактом.

## Запуск и права

После CSV + XML импорта, нормализации и завершённого matching откройте
«Открыть конфликты сопоставления» → «Проверить конфликты». Нужна существующая
`analysis.run` (REVIEWER/DATA_OWNER/ADMIN); просмотр — `conflict.view` для четырёх
канонических ролей. ADMIN не получает полномочий принимать бизнес-решение.

`POST /api/v1/conflict-runs {matching_run_id}` возвращает 201 и асинхронный запуск;
повторный запрос при активном запуске — 200 с тем же ID.
`GET /api/v1/conflict-runs` и `GET /api/v1/conflict-runs/{id}` показывают прогресс/ошибку.
Техническая ConflictRun использует существующий AnalysisRun lifecycle
NEW→QUEUED→PROCESSING→COMPLETED/FAILED, не вводя новый бизнес lifecycle.
Набор eligible MATCHED IDs фиксируется отдельной технической association в транзакции
создания запуска под блокировкой matching run. Последующие подтверждения matching
попадают в новый явный запуск. POSSIBLE_MATCH/NOT_MATCHED не создают business Conflict.

## Семантика

Версионированная release configuration: `backend/app/conflicts/profiles/default-v1.json`.
Она не является CustomerTemplate/Rule или Forest Codex. Forest Codex явно не настроен.

- VALUE_MISMATCH: оба normalized значения VALID, типы и канонические единицы одинаковы,
  значения различны. Decimal/quantity сравниваются численно; строки/даты — после правил
  нормализации. Tolerance = 0 зафиксирован конфигурацией. Matching tolerance не является
  бизнес-допуском атрибута. Новые допуски потребуют новой версии конфигурации.
- MISSING: одна сторона PRESENT, другая явно missing/null/empty. Эти причины различимы
  в evidence. В CSV/XLSX отсутствие колонки определяется по сохранённым header keys raw record; это SCHEMA_UNMAPPED, а не пустая ячейка. INVALID_OR_UNKNOWN и WARNING не подменяются отсутствием.
  При обоих отсутствующих значениях межсистемный конфликт не выдумывается.
- DUPLICATE: в замороженном MATCHED graph более одной записи одного источника
  подтверждены как идентичные одной записи второго. Сохраняются concrete peer raw IDs.
  Это не любой MatchCandidate, не physical merge и не правило уникальности произвольного
  клиентского ключа. Неподтверждённые повторяющиеся ключи остаются matching review.
- RULE_VIOLATION: canonical enum поддержан, generation выключен до Stage 11 versioned Rules.
- ANOMALY: canonical enum поддержан, generation выключен до утверждённого детектора.

Severity LOW — нейтральный технический default, не оценка бизнес-риска. Причина сохранена
в config snapshot. Никакой production severity policy или «истины» не выводится.
Conflict создаётся только OPEN. Все mutations и удаления Conflict запрещены DB guard;
будущий Stage 6/7 должен отдельной миграцией разрешить канонические переходы с Decision.

## Evidence и историчность

Conflict содержит ссылки на pre-match entity (не объединённую сущность), normalization
AnalysisRun, MatchingRun/MatchCandidate и два исходных значения. Сохраняются source IDs/names,
raw IDs, batch/file/hash/position, EntityValue IDs, raw/normalized snapshot, units, quality,
normalization context и matching evidence/profile snapshot/hash, conflict engine/config hash.
Большие/структурированные raw values не копируются: immutable raw/value IDs остаются
доступны, omission указан явно. Ни source payload, ни secret не пишутся в Audit.

GET списка возвращает только metadata и компактный source context. Detail показывает Basis,
unknown/invalid/presence, версии и «Решение человека ещё не принято». Если matching,
normalization или conflict config заменены, detail маркируется previous-profile;
история не пересчитывается молча. Новая оценка требует явного запуска.

## Idempotency и recovery

Conflict ID детерминирован по MatchCandidate, attribute, type, config hash и (для DUPLICATE) frozen peer raw IDs. Дополнительное подтверждение identity создаёт новую dependency set, не переписывая старое duplicate evidence.
Повторные delivery/rerun используют прежний immutable Conflict, технические outputs
связывают его с новой execution history. Новые matching executions имеют новые candidate IDs.
Обработка идёт keyset chunks по 100 identity, только их значения; O(matched pairs × attributes),
без cross-source Cartesian product. PostgreSQL advisory lock сериализует одну execution.
Evidence + per-conflict Audit + output + counters/checkpoint фиксируются атомарно.

При hard stop PROCESSING продолжается с checkpoint. Обычная ошибка даёт FAILED с безопасным
CONFLICT_INTERRUPTED; retry — новый технический запуск, прежние факты переиспользуются.
Worker startup/maintenance восстанавливает NEW, обнаруживает потерянные QUEUED/PROCESSING
и помечает FAILED; защитное окно 60s, maintenance 30s, idle dequeue до105s; занятый worker
проверяет после текущего задания. Это не SLA восстановления.

## Миграция и проверки

0006_conflicts добавляет только таблицы/индексы/guards; raw, normalization и matching
не backfill/merge. Upgrade с0005 и repeat, disposable-fixture downgrade/upgrade,
сохранность Stage2–4 и restart проверяются отдельно. Downgrade удаляет conflict history;
production rollback требует backup, не автоматического удаления истории.

Fixtures и oracle: [synthetic conflicts](../../tests/data/conflicts/README.md).
Unit/API/frontend/HTTPS browser tests сопровождаются полным regression/security набором.
Capacity: из backend `FK_TEST_INTEGRATION=1 uv run python -m tests.benchmark_conflicts
--records 100 1000 10000 100000` на disposable PostgreSQL/Redis. Два source×30attrs,
контролируемые изменения каждого10-го/20-го атрибута, точный expected count,
10 sessions, list/card p95, время и process peak RSS. Это инженерный benchmark, не SLA.

Human Review actions, Decision Registry, recommendations, AI, write-back и изменение
Forest Codex относятся к последующим этапам и отсутствуют.

При повторном benchmark только Conflict Engine можно использовать уже подготовленный
реальный disposable matching run без нового импорта: `FK_TEST_INTEGRATION=1 uv run python
-m tests.benchmark_conflicts_reuse --schema auth_test_<32hex> --matching-run <uuid>
--records 100000`. Это не независимый review и не повтор измерений Stage2–4:
новая execution текущего engine читает их immutable history. Probe держит DDL read locks
до конца проверки, использует отдельную очередь/пользователей и печатает exact SHA.
Схема должна принадлежать вызывающему тесту; её последующее удаление выполняет владелец.
Обычный полный benchmark выше остаётся основным воспроизводимым standalone путём.

[Pre-merge acceptance report and blockers](../testing/reports/stage5-conflicts-acceptance-2026-10-21.md).
