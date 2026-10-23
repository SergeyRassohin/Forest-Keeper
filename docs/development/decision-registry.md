# Stage 6: Decision Registry

Decision — append-only business fact в PostgreSQL, не поле статуса Conflict. [Human Review](human-review.md) описывает пользовательский путь и права. Physical UPDATE/DELETE запрещены DB trigger; API PATCH/DELETE отсутствуют.

Хранятся stable UUID; Conflict/entity/domain/business key/attribute; server actor ID, имя и роли на момент решения; UTC timestamp; canonical outcome/value/type/unit; source/value references; corrected input/trace; reason; historical context; schema version; evidence hash и review token; persistent idempotency key/request hash; supersedes Decision ID; audit event ID.

Historical context содержит frozen Conflict/Basis/обе стороны со ссылками на RawRecord/EntityValue/файл/позицию/хеш; normalization profile version/hash, matching profile/hash/snapshot/input context; Conflict Engine/config version/hash. Большие raw payload не дублируются; доступен оригинал через прежний provenance. Forest Codex явно unconfigured, authority NOT_DEFINED; текущая конфигурация не переинтерпретирует прошлое решение.

ACTIVE/SUPERSEDED вычисляются по наличию successor. Старый Decision физически не меняется. Unique root на Conflict, unique successor и same-case predecessor FK дают линейную историю без ветвей; predecessor обязан уже существовать. Conflict.current_decision_id указывает на единственный head. Все чтения нового реестра и очереди Conflict фильтруются server-side data_domains, включая detail/history/retry receipt.

## API

| Метод | Путь `/api/v1` | Назначение |
| --- | --- | --- |
| GET | `/conflicts/{id}/review-context` | Frozen evidence, version token, permitted actions, policy, head, history count |
| POST | `/conflicts/{id}/review` | Явное начало/пересмотр; token + supersedes_decision_id |
| POST | `/conflicts/{id}/decisions` | Атомарное сохранение; 201 либо 200 idempotent replay |
| GET | `/decisions/{id}` | Полная неизменяемая запись и historical context |
| GET | `/conflicts/{id}/decisions` | История, UTC timestamp + ID ASC, limit/offset |
| GET | `/decisions` | Лёгкий реестр без больших context/trace, UTC timestamp + ID DESC |
| PUT | `/users/{id}/data-scope` | Явное назначение области данных администратором |

Фильтры реестра: conflict_id, entity_id, business_key (точное совпадение), attribute_code, user_id, decision_type, status, date_from/date_to (только aware datetime). limit 1–100, default 50, offset 0–1 000 000. Пагинация детерминирована для неизменного набора; при новых конкурентных вставках offset-пагинация не является snapshot cursor.

POST Decision: context_version (SHA-256 hex), idempotency_key (UUID), decision_type, reason, confirmed=true, optional supersedes_decision_id; для SELECT_VALUE selected_source_id/selected_value_id; для ENTER_VALUE corrected_value/corrected_unit. Остальные поля запрещены. 401 — сессия, 403 — права/Origin, 404 — объект отсутствует или вне scope, 409 — stale/head/key/несовместимый контекст, 422 — схема/значение, 503 — сохранение не подтверждено. При 503 повторять **тот же** payload/key.

## Migration и recovery

0007_decisions: таблица/индексы/constraints/append-only trigger, узко разрешённый lifecycle guard Conflict, deferred head integrity, review_version/current_decision_id и User.data_domains. Старые source/import/normalized/matching/Conflict факты остаются. Health требует новую revision. Empty downgrade → upgrade допустим; downgrade при существующей Decision history **отклоняется**, не стирает решения. Для rollback релиза с историей нужен проверенный backup и отдельный план, не удаление business data.

PostgreSQL — authority. Human Review не ставит jobs, не требует LLM/vector retrieval и не зависит от Redis для сохранения уже аутентифицированного запроса. Login/rate limiting и health продолжают использовать Redis. После восстановления БД повторить отправку тем же key; если commit состоялся, читается исходный Decision. Повторная доставка HTTP не создаёт новый business audit.

## Ограничения

История не является электронной подписью/криптографическим доказательством против DB superuser. Hash фиксирует integrity context, не присваивает истину. Нет удаления/редактирования Decision, publisher, source write-back, AI, similarity или автоматического изменения правил/Gold Reference. Эти функции требуют отдельного принятого этапа. Роли/permissions не расширялись; domain scope — отдельный явный слой доступа нового workflow.
