# Forest Keeper — API Contract v0.1

Статус: рабочий контракт для MVP.

## 1. Зачем этот документ

API — это договорённость между браузерным интерфейсом Forest Keeper и сервером.

Пользователь нажимает кнопку в браузере, frontend отправляет запрос серверу, сервер выполняет действие и возвращает структурированный ответ.

Для MVP API должен поддержать первый полный сценарий:

**файл → импорт → анализ → конфликт → решение человека → сохранённый прецедент → рекомендация при похожем случае.**

---

## 2. Общие правила

- Транспорт: HTTPS.
- Формат данных: JSON.
- Версия API: `/api/v1`.
- Идентификаторы сущностей: UUID.
- Даты и время: ISO 8601.
- Файлы загружаются через `multipart/form-data`.
- Все изменения данных журналируются.
- AI/LLM не пишет напрямую в мастер-данные и внешние системы.
- Любое финальное решение по конфликту подтверждает человек.
- Ошибки возвращаются в едином формате.

Пример ошибки:

```json
{
  "error": {
    "code": "CONFLICT_NOT_FOUND",
    "message": "Конфликт не найден",
    "details": {}
  }
}
```

---

## 3. Авторизация

### POST /api/v1/auth/login

Вход пользователя.

Запрос:

```json
{
  "login": "sergey",
  "password": "********"
}
```

Ответ:

```json
{
  "user": {
    "id": "uuid",
    "display_name": "Сергей",
    "roles": ["DATA_OWNER"]
  }
}
```

### GET /api/v1/auth/me

Возвращает текущего пользователя и его роли.

### Реализация этапа 1

Локальная аутентификация использует отзываемые opaque-сессии. Единственный клиент MVP — браузер. Он получает Secure/HttpOnly/SameSite=Strict cookie `__Host-fk_session`; JSON login содержит только user, без идентификатора сессии. Авторизация через заголовок не поддерживается: Authorization на защищённом маршруте даёт 401. Login и изменяющие запросы с cookie требуют Origin из списка разрешённых; отсутствующий, null или сторонний Origin даёт 403. Ответ user содержит актуальные permissions вместе с ролями, full_name и job_title. Добавлен `POST /api/v1/auth/logout` (204), отзывающий текущую сессию. Детали cookie/CSRF, административного создания пользователей и проверок: [Authentication + RBAC](../development/authentication.md).

---

## 4. Источники данных

### GET /api/v1/sources

Список настроенных источников.

### POST /api/v1/sources

Создать источник.

Пример:

```json
{
  "code": "one_c_main",
  "name": "1С основная",
  "source_type": "ONE_C"
}
```

### GET /api/v1/sources/{source_id}

Карточка источника.

### PATCH /api/v1/sources/{source_id}

Изменение настроек источника.

Этап2: source_type принимает FILE (CSV/XLSX/generic XML) или ONE_C (тот же файловый источник с тестовым 1С XML профилем). Создание требует source.manage; чтение — source.view. Созданный источник имеет status ACTIVE и authority_scope={} по умолчанию. PATCH меняет только name/authority_scope; code/source_type/status не являются произвольными editable полями. Уникальный code уже существует →409. Поле authority_scope на этом этапе хранит metadata без определения истинности значений.

---

## 5. Импорт файлов

### POST /api/v1/imports

Загрузить файл и создать пакет импорта.

Параметры:

- `source_id`
- файл

Тело `multipart/form-data`: поля `source_id` (UUID) и `file`; остальные поля не нужны. Обязательны cookie, разрешённый Origin и permission import.create. Лимит файла —100000000байт по умолчанию. Неподдерживаемое расширение→415, небезопасное имя→422, превышение размера→413, неактивный источник→409. Небезопасный/повреждённый файл с допустимым расширением сохраняется как оригинал, но worker завершает пакет FAILED с безопасной ошибкой.

Ответ:

```json
{
  "import_batch_id": "uuid",
  "status": "QUEUED",
  "file_name": "materials.xlsx",
  "duplicate": false
}
```

Новая загрузка возвращает201 и ImportView; разбор выполняется через RQ. Ответ дополнительно содержит id/import_batch_id, source_system_id/source_name, original_filename/file_name, format, file_hash (SHA-256), uploaded_by/uploaded_at, records_total/records_loaded/records_failed, error_text и retry_of_id. Storage URI и серверный filesystem path не выдаются. При недоступной очереди принятый пакет может уже иметь FAILED;201 подтверждает сохранение оригинала/пакета, а не завершение импорта.

Идентичные байты для того же source_id возвращают200 с `duplicate=true` и тем же первичным ImportBatch; новое имя не перезаписывает первое, новая задача и RawRecord не создаются. У другого источника тот же файл создаёт отдельный пакет. Конкурентные дубликаты защищены уникальным индексом PostgreSQL.

При исчерпании места/квоты диска до регистрации загрузки POST `/imports` возвращает HTTP507
`STORAGE_FULL` с безопасным сообщением. Временные файлы и неуспешный оригинал освобождаются;
пакет не регистрируется. После освобождения места можно повторить исходный POST.

### GET /api/v1/imports

Список ImportView от новых к старым; import.view. Общие параметры страниц списка источников/импортов/records/errors: limit1–100 (default50), offset0–1000000. UI использует страницы50.

### GET /api/v1/imports/{import_batch_id}

Статус импорта.

Ответ:

```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "records_total": 1542,
  "records_loaded": 1542,
  "records_failed": 0
}
```

### GET /api/v1/imports/{import_batch_id}/errors

Ошибки разбора файла.

Ответ — массив `{id, source_position, code, message}`; сообщения не содержат исходный payload, credentials или filesystem internals. Требуется import.view. Ошибка отдельной строки/объекта оставляет другие записи; результат COMPLETED_WITH_ERRORS. Нечитаемый документ или пакет без пригодных записей при ошибках — FAILED.

### GET /api/v1/imports/{import_batch_id}/records

Минимальный просмотр RawRecord, import.view: массив `{id, import_batch_id, source_record_key, source_object_type, raw_payload, source_position, created_at}`. Записи неизменяемы; source_position указывает строки CSV, sheet/row XLSX или номер XML-объекта. Исходный пакет связывает их с источником и оригинальным файлом. Сервер возвращает страницы в стабильном порядке created_at/id; это не обещание сортировки по исходному номеру строки.

### POST /api/v1/imports/{import_batch_id}/retry

Permission import.retry, cookie и разрешённый Origin. Для FAILED/COMPLETED_WITH_ERRORS создаёт201 новый ImportBatch (retry_of_id), ссылающийся на тот же неизменяемый оригинал. Старый статус/RawRecord/errors не меняются. Активный повтор того же пакета или повтор успешного пакета→409. Повторный upload остаётся duplicate первичного пакета; повторную обработку нужно запросить явно.

Все endpoints источников/импорта проверяют permission backend и возвращают no-store. Форматы, лимиты парсеров, базовый профиль 1С и восстановление очереди: [Import subsystem](../development/import.md).

---

## 6. Запуск анализа / нормализация (Этап 3)

`POST /api/v1/analysis` использует существующий permission `analysis.run`, cookie и разрешённый Origin. В Этапе 3 выполняется **только нормализация**: matching/conflicts не запускаются. Неизвестные данные не угадываются и normalized не объявляется истиной.

```json
{"import_batch_ids": ["uuid-1", "uuid-2"], "template_id": "mapping-profile-uuid"}
```

От 1 до 20 разных ImportBatch со статусом COMPLETED/COMPLETED_WITH_ERRORS. `template_id` выбирается из GET `/api/v1/analysis/profiles`; пока это UUID декларативного app-config profile, не workflow CustomerTemplate. Поставляемые profiles синтетические. Snapshot mapping, version, engine/rules version и SHA-256 сохраняются с запуском.

Новый запуск возвращает201 и AnalysisView: id/analysis_id, status, import_batch_ids, template_id, mapping_hash, mapping_snapshot, actor_id, records_processed, values_processed, quality_counts, created_at, completed_at, error_text. Статус после приёма обычно QUEUED;201 не означает успешное завершение. Если точно такой scope/profile уже активен, возвращается200 и его id. Повтор после terminal status создаёт новый AnalysisRun, история сохраняется; semantic facts не дублируются для того же raw/fingerprint. При отказе публикации очередь получает FAILED с безопасным code. Structural validation→422; неизвестный import→404, незавершённый/FAILED import→409.

`GET /api/v1/analysis/profiles`, `GET /api/v1/analysis?import_batch_id=uuid`, `GET /api/v1/analysis/{analysis_id}` и `GET /api/v1/analysis/{analysis_id}/records` требуют существующий `analysis.view`. Списки: limit1–100 (default50), offset0–1000000. Порядок запусков created_at/id desc; порядок записей raw_record_id. Новые маршруты возвращают no-store; unauthenticated→401, permission denied→403. Read endpoints не выполняют нормализацию и не меняют состояния.

Records response: raw_record_id, source_record_key, source_position, raw_payload, source{id,name,code}, import_batch{id,original_filename,file_hash}, entity{id,domain,entity_type,display_name,status}, values, mapping_details. Каждый value содержит id, attribute_code, raw_record_id, raw_value, normalized_value, unit, quality_status, normalization_rule и точную rule_definition из сохранённого snapshot. Entity nullable для неподдержанного object type. `status` CanonicalEntity зарезервирован NULL, не является lifecycle состоянием. Записи разных источников остаются разными entity.

Normalized decimal/quantity сериализуется строкой без binary-float арифметики, дата — YYYY-MM-DD. Quality: VALID/WARNING/INVALID/UNKNOWN. `normalization_rule` ссылается на mapping fingerprint/field, содержит presence/reason/conversion evidence. Пропущенное поле, JSON null и пустая строка различаются по presence. Unknown fields не становятся вымышленными canonical attributes: они перечислены в mapping_details как UNKNOWN, с неизменяемым raw_payload рядом. `quality_counts` считает сохранённые EntityValue; непокрытые mapping поля/объекты диагностируются отдельно в record details.

До COMPLETED результаты частичные; FAILED сохраняет уже записанные chunks и code NORMALIZATION_INTERRUPTED без внутренних путей/raw. Retry — новый POST с теми же imports/profile, никаких reset FAILED→PROCESSING. Recovery и гарантии checkpoints описаны в [normalization subsystem](../development/normalization.md). Поля matches_found/conflicts_found относятся к будущим этапам и сейчас не выдаются как вычисленные результаты.

---

## 7. Конфликты — Stage 5 PR

Контракт реализован в ветке Stage 5; до acceptance/merge он не означает готовности main.
Подробная семантика и recovery: [Conflict Engine](../development/conflicts.md).

### POST /api/v1/conflict-runs

Cookie + разрешённый Origin + `analysis.run`. Body: `{ "matching_run_id": "uuid" }`.
MatchingRun должен быть COMPLETED. 201 создаёт асинхронную техническую execution;
200 возвращает текущий активный запуск для того же matching/config. MATCHED IDs фиксируются
при создании; новые matching reviews требуют нового запуска. Ни один GET не запускает analysis.

### GET /api/v1/conflict-runs и GET /api/v1/conflict-runs/{id}

`conflict.view`. Список: limit1–100 (default50), offset0–1000000, newest created_at/id first.
Detail: status NEW/QUEUED/PROCESSING/COMPLETED/FAILED, matching_run_id, profile_hash/snapshot,
records_processed, attributes_evaluated, conflicts_generated, status_counts (type breakdown),
created_at/completed_at/error_text. FAILED/partial не выдаётся за completed.
`conflicts_generated` считает outputs этого execution, включая повторно использованные
immutable Conflict, а не newly inserted rows. `status_counts` — те же outputs по conflict type,
не по lifecycle status. Rerun может иметь ненулевые counters без новых Conflict/creation Audit;
duplicate delivery завершённого запуска ничего не добавляет.

### GET /api/v1/conflicts

`conflict.view`: VIEWER/REVIEWER/DATA_OWNER/ADMIN по canonical access matrix.
Ответ — массив компактных metadata, как в существующих import/analysis/matching API.
Фильтры: conflict_type, status, severity, entity_id, matching_run_id, source_id.
Pagination: limit1–100/default50, offset0–1000000; порядок detected_at DESC, id DESC.
Недопустимые enum/UUID/pagination →422 INVALID_REQUEST. Без роли →403; без сессии →401.
Ответ не содержит values_snapshot/Basis. Source context: source_id/name/record key.
`source_id` проверяется в любой стороне values_snapshot (JSONB array containment);
неизвестный источник возвращает пустой массив. Фильтры комбинируются через AND.
Одиночный `analysis_run_id` — первый normalization input matching, не полный набор origins.

```json
[{
  "id": "uuid", "entity_id": "uuid", "analysis_run_id": "uuid",
  "matching_run_id": "uuid", "match_candidate_id": "uuid",
  "attribute_code": "mass", "conflict_type": "VALUE_MISMATCH",
  "severity": "LOW", "status": "OPEN", "detected_at": "UTC timestamp",
  "sources": [{"source_id": "uuid", "source_name": "CSV", "source_record_key": "DIFF"}]
}]
```

### GET /api/v1/conflicts/{conflict_id}

Metadata + values_snapshot (две source/provenance/value стороны) + Basis.
Values: raw/normalized/unit/quality, immutable EntityValue ID, normalization_rule,
raw_record_id/entity_id, source_id/name, import_batch_id/filename/hash/position/record key.
Presence различает PRESENT/MISSING/NULL/EMPTY/SCHEMA_UNMAPPED/INVALID_OR_UNKNOWN.
Большое/структурированное raw отмечается raw_value_omitted, исходная ссылка сохраняется.
Basis: deterministic reason, authority NOT_DEFINED, matching evidence и profile snapshot/hash,
normalization context, engine/config snapshot/hash, human_decision NOT_TAKEN.
`basis.normalization_context.normalization` сохраняет оба `analysis_id`, `source_id`,
`profile_id`, `mapping_hash` и `engine_version`. Дополнительный `normalization_origins`
повторяет этот frozen context и добавляет `profile_version` из immutable AnalysisRun snapshot
каждой стороны. Это полный lineage; `analysis_run_id` не означает единственный источник.
`based_on_previous_profile` явно обозначает dependency drift; Forest Codex пока не настроен.
Неизвестный ID →404 CONFLICT_NOT_FOUND. Все ответы private/no-store.

Enums: VALUE_MISMATCH/MISSING/DUPLICATE/RULE_VIOLATION/ANOMALY;
OPEN/IN_REVIEW/RESOLVED/INSUFFICIENT_DATA; LOW/MEDIUM/HIGH/CRITICAL.
Stage 5 создаёт только OPEN/LOW. LOW — нейтральный technical default, не бизнес-риск.
RULE_VIOLATION/ANOMALY generation выключен до пригодных versioned rule/detector.
Примеры Decision/recommendation ниже исторические. Фактический Human Review Stage 6 и отдельная реализация Stage 8 описаны в актуальных разделах в конце документа; исторические DTO не являются текущим wire contract.

---

## 8. Решение пользователя

### POST /api/v1/conflicts/{conflict_id}/decisions

Пользователь фиксирует решение.

Допустимые `decision_type` для MVP:
- `SELECT_VALUE` — выбрать одно из представленных/нормализованных значений; при выборе конкретного источника передаётся `selected_source_id`;
- `ENTER_VALUE` — пользователь вводит и подтверждает другое значение;
- `INSUFFICIENT_DATA` — данных недостаточно для определения результата;
- `DEFERRED` — решение явно отложено и конфликт не считается RESOLVED.

Все Decision создаются только подтверждённым действием пользователя; отдельный тип `HUMAN_CONFIRMED` не используется.

Пример:

```json
{
  "decision_type": "SELECT_VALUE",
  "selected_value": "12.5",
  "comment": "Для массы этого типа материала считаем 1С доверенным источником"
}
```

Сервер обязан:

1. сохранить решение;
2. сохранить контекст конфликта на момент решения;
3. записать пользователя и время;
4. изменить статус конфликта;
5. добавить решение в историю прецедентов;
6. создать событие аудита.

Ответ:

```json
{
  "decision_id": "uuid",
  "conflict_status": "RESOLVED"
}
```

### GET /api/v1/conflicts/{conflict_id}/decisions

История решений по конфликту.

---

## 9. Рекомендации Forest Keeper

### GET /api/v1/conflicts/{conflict_id}/recommendation

Получить рекомендацию для текущего конфликта.

Ответ:

```json
{
  "id": "uuid",
  "recommended_action": {
    "decision_type": "SELECT_VALUE",
    "selected_value": "12.5"
  },
  "confidence": 0.86,
  "reasoning_summary": "В 8 похожих подтверждённых случаях пользователь выбирал значение из 1С.",
  "similar_decisions": [
    {
      "decision_id": "uuid",
      "similarity": 0.93
    }
  ],
  "rules_used": [
    "material_mass_source_priority"
  ]
}
```

Ключевой принцип: рекомендация не считается решением и ничего не меняет без подтверждения человека.

---

## 10. Похожие прошлые решения

### GET /api/v1/conflicts/{conflict_id}/similar-decisions

Возвращает подтверждённые ранее решения, наиболее похожие на текущий случай.

Параметры:

- `limit`
- `min_similarity`

Ответ:

```json
{
  "items": [
    {
      "decision_id": "uuid",
      "similarity": 0.93,
      "summary": "Для массы материала выбран источник 1С",
      "created_at": "2026-09-10T09:30:00Z"
    }
  ]
}
```

---

## 11. Правила

### GET /api/v1/rules

Список действующих правил.

### POST /api/v1/rules

Создать правило вручную.

### PATCH /api/v1/rules/{rule_id}

Изменить правило.

### POST /api/v1/rules/{rule_id}/activate

Активировать правило.

### POST /api/v1/rules/{rule_id}/deactivate

Отключить правило.

---

## 12. Предложение нового правила на основе истории решений

### GET /api/v1/rule-suggestions

Список закономерностей, которые Forest Keeper предлагает превратить в формальное правило.

Пример:

```json
{
  "items": [
    {
      "id": "uuid",
      "summary": "В 12 из 12 похожих случаев для атрибута mass выбиралось значение из 1С",
      "suggested_rule": {
        "entity_type": "Material",
        "attribute_code": "mass",
        "preferred_source": "one_c_main"
      }
    }
  ]
}
```

### POST /api/v1/rule-suggestions/{suggestion_id}/accept

Человек подтверждает создание правила.

### POST /api/v1/rule-suggestions/{suggestion_id}/reject

Человек отклоняет предложение.

Forest Keeper не должен активировать новое правило без подтверждения пользователя.

---

## 13. Шаблон заказчика

### GET /api/v1/templates/current

Получить текущий шаблон клиента.

### PATCH /api/v1/templates/current

Изменить настройки шаблона.

### POST /api/v1/templates/current/reset

Вернуться к базовому шаблону FK.

Перед сбросом требуется явное подтверждение пользователя.

---

## 14. Канонические сущности

### GET /api/v1/entities

Поиск и список канонических сущностей.

### GET /api/v1/entities/{entity_id}

Карточка сущности с атрибутами и provenance.

### GET /api/v1/entities/{entity_id}/history

История изменений и подтверждений.

---

## 15. Аудит

### GET /api/v1/audit

Журнал действий.

Фильтры:

- пользователь;
- тип события;
- объект;
- период.

Аудит должен позволять восстановить, кто, когда и на основании чего изменил состояние данных или правил.

---

## 16. Системная информация

### GET /api/v1/health

Техническая проверка доступности сервера.

### GET /api/v1/version

Версия Forest Keeper.

### GET /api/v1/license

Текущее состояние лицензии без раскрытия служебных секретов.

Коды модулей и состояния лицензии должны совпадать с `docs/licensing/licensing-v0.1.md` и `docs/development/object-lifecycles-v0.1.md`; API не вводит отдельные наборы названий. Допустимые состояния lifecycle: `ACTIVE`, `GRACE_PERIOD`, `READ_ONLY`, `INVALID`.

Пример:

```json
{
  "edition": "Enterprise",
  "valid_until": "2027-10-01",
  "modules": ["core", "entity-resolution", "recommendations"],
  "status": "ACTIVE"
}
```

---

## 17. Что не входит в API v0.1

Пока не фиксируем окончательно:

- прямую запись данных обратно в 1С/ERP/PLM;
- автоматическое изменение корпоративных мастер-данных;
- сложные массовые workflow согласования;
- внешние публичные API для партнёров;
- обучение собственной нейросети после каждого решения;
- vendor-specific интеграционные контракты.

Это будет добавляться после первого рабочего вертикального сценария.

---

## 18. Минимальный набор endpoint'ов для первого вертикального прототипа

Чтобы начать разработку, достаточно реализовать сначала только:

1. `POST /api/v1/imports`
2. `GET /api/v1/imports/{id}`
3. `POST /api/v1/analysis`
4. `GET /api/v1/conflicts`
5. `GET /api/v1/conflicts/{id}`
6. `POST /api/v1/conflicts/{id}/decisions`
7. `GET /api/v1/conflicts/{id}/recommendation`
8. `GET /api/v1/conflicts/{id}/similar-decisions`

Если этот набор работает от начала до конца, Forest Keeper уже умеет выполнить основную идею MVP, а не просто гордо содержать папку `docs`.

## Stage 4 — Matching API

Нормализация `/analysis` сохраняет прежнюю семантику; её completed runs не переоткрываются. Matching не создаёт Conflict.

- `GET /api/v1/matching-profiles` — декларативные profiles UUID/code/version/domain/entity_type/hash, право `match.view`.
- `POST /api/v1/matching-runs` — `analysis.run`, cookie + Origin; `{analysis_run_ids:[uuid,uuid],profile_id:uuid}`. Два разных completed normalized inputs, каждый одного источника, совместимые domain/entity_type и disjoint ImportBatch scope. Default cross-source; same-source требует явного profile flag. 201 новый run, 200 тот же активный scope/hash. После terminal — новый run/history. Ошибки:422 incompatible input/profile,409 input not ready,404 input missing,503 queue unavailable.
- `GET /api/v1/matching-runs?limit=50&offset=0` и `GET .../{id}` — `match.view`. DTO: id,status,input_analysis_ids,input_context,profile_id/hash/snapshot,actor_id,records_processed,candidates_generated,status_counts,diagnostics,created_at,completed_at,error_text,based_on_previous_profile,gold_reference_configured. Lifecycle только canonical AnalysisRun. До COMPLETED results partial. Coverage limits всегда доступны отдельно, completed не обещает исследование всех Cartesian pairs. Gold Reference явно unconfigured.
- `GET /api/v1/matching-runs/{id}/candidates?status=POSSIBLE_MATCH&limit=50&offset=0` — `match.view`, status optional canonical3values. Summary: id,run_id,raw_record_a_id,raw_record_b_id,confidence (Decimal string six places),status,confirmed_by,created_at,reason (исходный engine reason). confirmed_by означает отдельное human review, которое не заменяет historical engine evidence.
- `GET /api/v1/match-candidates/{id}` — summary + full evidence/signals/blocking/input version context, оба source/raw/normalized/provenance records, frozen run view и nullable manual_review из Audit (audit_event_id,actor_id,reviewed_at,from_status,to_status,reason). Engine reason и human reason разделены.
- `POST /api/v1/match-candidates/{id}/review` — существующее `match.review`, cookie + Origin; `{status:"MATCHED"|"NOT_MATCHED",reason:nonempty string≤1000}`. Только POSSIBLE_MATCH завершённого run; actor в confirmed_by, audit и atomic counters. Terminal/repeated/concurrent loser→409. ADMIN без REVIEWER/DATA_OWNER→403.

Read pagination limit1..100, offset0..1000000; matching/analysis private responses no-store. No header bearer mode. Политика threshold OPEN, fuzzy не получает автоматический MATCHED. [Подсистема, ограничения, history/currentness и recovery](../development/matching.md).


## Stage 6: реализованный Human Review API

Актуальные POST/GET endpoints, DTO, ошибки, scope и pagination описаны в [Decision Registry](../development/decision-registry.md#api). Decision PATCH/DELETE отсутствуют. Cookie + Origin; actor только из сессии. Create требует version token, UUID idempotency_key, reason и explicit confirmed=true. Результат возвращается после атомарного commit. Старый target recommendation DTO заменён контрактом Stage 8 ниже; Stage 7 similarity GET сохраняет прежний контракт.

## Stage 7: реализованный similarity GET (issue #27)

`GET /api/v1/conflicts/{id}/similar-decisions?limit=5&offset=0`: cookie authentication, conflict.view + decision.view + explicit data_domains. Limit 1..20, offset 0..100, other query fields rejected422. Earlier target min_similarity override is superseded: threshold>=0.85 is immutable versioned server configuration. Full response/state/reason/security contract: [Similarity Retrieval](../development/similarity-retrieval.md#api-и-ui). Unavailable counts are null; этот retrieval endpoint не возвращает готового действия и не записывает Decision.

## Stage 8: deterministic recommendation API (PR #30, приёмка продолжается)

`GET /api/v1/conflicts/{id}/recommendation` использует cookie-session, существующие
`conflict.view`, `decision.view`, `recommendation.view` и domain scope. Любой query
override →422. Нет доступа к объекту / неизвестный UUID → одинаковый404. Ответ
private/no-store. Auth и evidence читаются в единой read-only REPEATABLE READ snapshot.

`status` результата — `RECOMMENDED | ABSTAINED | UNAVAILABLE`, а не lifecycle
Conflict/Decision/Recommendation. `recommended_action` = `SELECT_VALUE` только для
положительного test/demo результата; source/value IDs всегда из текущего Conflict.
`confidence` = число независимых provenance-групп (5..20), unit
`INDEPENDENT_PROVENANCE_GROUPS`; это не вероятность и не cosine similarity.
При отказе action/source/value/confidence = null, supporting_decision_ids = [].
Reason, объяснение, scoped evidence с действительными Decision IDs, противоречия,
ограничения, quality_provenance, policy/model/retrieval/mapping versions,
review_context_version, context_fingerprint, generated_at и audit_reference описаны
в [фактическом контракте](../development/recommendations.md).
Rules/Template/Codex = NOT_CONFIGURED; authority = NOT_DEFINED. Production fail-closed.

GET не меняет бизнес-факты и не запускает embedding/RQ; допускается отдельный bounded
append-only audit receipt после закрытия read-only snapshot. Общий со Stage 7 лимит
120 authenticated reads/min/actor; protective total SQL/lock budget1500ms.

Существующий `POST /conflicts/{id}/decisions` принимает необязательный
`recommendation_reference: UUID`. Только при его наличии нужно дополнительное
существующее permission `recommendation.accept_as_decision`; сервер заново проверяет
receipt/политику/evidence/token под transaction gate, stale →409. Ручные reason,
confirmed=true, версия, idempotency key и все прежние права обязательны.
Точный committed retry возвращает прежний receipt даже при недоступном Redis.
Без reference ручное сохранение независимо от Recommendation/embedding.
Новый Decision может содержать additive context_snapshot.recommendation; старые
факты не переписываются. PATCH/DELETE и автоматического Decision нет.

### Stage 9 optional local AI explanation (development, not accepted production)

The explicit cookie/Origin-authenticated `POST /api/v1/conflicts/{id}/ai-explanation`
accepts only `{ "request_id": "UUID", "language": "ru" }` (`en` also supported) and
returns202`{ "request_id": "opaque UUID handle" }`. Retrying the same client request ID
in the same session/case is idempotent. Required permissions are `conflict.view`,
`decision.view` and `recommendation.view`, plus current case scope. Production is disabled.

`GET /api/v1/conflicts/{id}/ai-explanations/{handle}` polls derived execution state
QUEUED/PROCESSING/COMPLETED/FAILED; it never runs inference. A completed response contains
validated factual clauses, existing evidence links and pinned model/prompt/schema identity.
Only the requesting actor/session/case can read it. Fresh scope, case/head and all relevant
configuration/evidence digests are checked before inference and completed delivery.
Stale, malformed or unavailable output produces a bounded failure, without model prose.
POST the polling URL with `/cancel` and no body marks logical discard. Active computation
can finish within its resource bound; cancellation cannot publish its result.

These routes do not create or prefill a Decision. Current review token, human reason,
confirmation and existing business permissions remain required for a manual Decision.
Model-facing `/internal/ai/*` routes belong to separate private model services and are
not registered on the public backend. Input bodies, prompts and vectors are not audited;
only bounded IDs, digests, clause codes and duration are recorded.
