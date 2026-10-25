# Stage 6: Human Review

Stage 6 принят владельцем по [issue #25](https://github.com/SergeyRassohin/Forest-Keeper/issues/25) через PR #26, main `0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852`, exact merge CI `39947944543` SUCCESS. Stage 7 bounded retrieval впоследствии принят через PR #28; Stage 8 реализован отдельно в PR #30 по утверждённой владельцем policy и проходит приёмку: [контракт](recommendations.md). Ручной путь сохраняется, новых бизнес-прав или AI нет.

Conflict фиксирует расхождение. Decision отдельно фиксирует действие человека над конкретным historical evidence. Evidence, raw/normalized values, matching и исходные системы не переписываются. Recommendation/AI/similarity/write-back не входят в этап.

## Путь в браузере

1. ADMIN создаёт пользователя REVIEWER или DATA_OWNER и явно назначает область данных в разделе «Пользователи → Область данных». Для учебных файлов можно разрешить все области. По умолчанию новый пользователь не видит Conflict/Decision. Одной роли ADMIN недостаточно для бизнес-решений.
2. Пользователь открывает «Конфликты», выбирает сопоставление и фильтр состояния. Перед действиями видит оба источника, raw/normalized значения, единицы, provenance, Basis и версии.
3. Нажимает «Начать рассмотрение». GET карточки не меняет lifecycle. Для исправления уже существующего решения используется явное «Пересмотреть решение».
4. Выбирает источник A/B, другое допустимое значение, «Недостаточно данных» либо «Рассмотрение отложено». Обоснование обязательно для всех исходов, 1–2000 символов. Отсутствующее/UNKNOWN/INVALID значение не становится истиной через SELECT_VALUE.
5. Проверяет итог в диалоге и явно подтверждает сохранение. Только ответ сервера даёт receipt с ID, автором, временем, значением, объяснением и historical context.
6. Открывает решение в реестре. После refresh/повторного входа решение читается из PostgreSQL. Исправление создаёт новую запись и сохраняет прежнюю.

## Outcomes и lifecycle

| DecisionType | Результат Conflict | Смысл |
| --- | --- | --- |
| SELECT_VALUE | RESOLVED | Выбрана допустимая frozen source/value reference A или B |
| ENTER_VALUE | RESOLVED | Введено другое каноническое значение; source data не меняются |
| INSUFFICIENT_DATA | INSUFFICIENT_DATA | Данных для значения недостаточно; selected_value = null |
| DEFERRED | IN_REVIEW | Рассмотрение оставлено незавершённым; selected_value = null |

OPEN → IN_REVIEW выполняет отдельная команда review start. RESOLVED/INSUFFICIENT_DATA → IN_REVIEW разрешён только для явного пересмотра с текущим Decision ID и permission decision.supersede; прежний head сохраняется до новой транзакции. Новая загрузка создаёт новый случай, не переоткрывает старый автоматически. См. [Decision Log](../decisions/decision-log.md).

## Авторизация и валидация

Используются существующие permissions XLSX: conflict.view, conflict.review.start, decision.view/create/insufficient_data/supersede. VIEWER только читает. ADMIN управляет доступом, бизнес-полномочия не наследуются из административной роли. Сессия HTTPS cookie + проверка Origin на POST, без bearer. Actor/roles берутся сервером; mass assignment запрещён.

`User.data_domains`: коды областей (до 32), пустой список запрещает новый Conflict/Decision scope; `['*']` — явно выданный доступ ко всем областям. Миграция сохраняет исторически глобальный доступ старых аккаунтов как явный wildcard. Назначение scope требует user.manage + role.assign и аутентификации не старше 5 минут, журналируется. Это не объявление полной tenant isolation всех прежних ingestion endpoints.

SELECT_VALUE требует совпадения source ID/value ID/value/type/unit с frozen Conflict. ENTER_VALUE доступен только при однозначных frozen kind/unit: string, decimal, quantity, date. Десятичная запятая нормализуется без округления, действуют пределы существующего normalizer (38 цифр, exponent ±18). Дата строго ГГГГ-ММ-ДД, без неоднозначного часового пояса. Сохраняются введённый текст и conversion trace. Нет придуманных business ranges. Строки отображаются React как текст; HTML не исполняется.

## Повторная отправка, конкуренция и сбои

`context_version` связывает evidence hash, lifecycle version и effective head. При stale token/head сервер возвращает 409; UI убирает устаревший draft и требует перечитать evidence. History pagination не заменяет token редактируемой формы.

UUID idempotency_key хранится столько же, сколько Decision. Scope ключа: actor + Conflict. Та же нагрузка возвращает прежний ID (200), другой payload с тем же ключом — 409. Сначала повторно проверяются текущие права и scope; старый receipt не обходит отзыв доступа. После неизвестного сетевого результата UI повторяет точно прежний payload/key. После restart механизм остаётся в PostgreSQL, Redis не является журналом решений.

Row lock на Conflict сериализует конкурентов; unique root/successor и deferred FK/trigger оставляют один head. Decision + effective head + lifecycle + business audit коммитятся вместе. Ошибка аудита/БД откатывает всё. При сбое после commit retry возвращает уже существующую запись. Отдельный sanitized rejection audit не содержит reason/corrected value/credentials. DB outage возвращает общий 503, без SQL параметров. Recovery не принимает решение вместо человека.

## Проверки

`test_decision_validation.py`, `test_decisions_integration.py`, `HumanReview.test.tsx`, `tests/e2e/decisions.spec.ts`, реальная [галерея](../../frontend/public/interface/index.html). Общие gates: [testing strategy](../testing/testing-strategy-v0.1.md). Подробности хранения: [Decision Registry](decision-registry.md).


## Воспроизведение runtime acceptance

Все команды ниже предназначены только для собственного изолированного тестового стенда. Для общего/default Compose и производственных данных harness откажется запускаться.

```bash
# После real browser E2E, с переменными БД своего fk-stage6 проекта:
cd backend
FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.restart_decisions \
  --project fk-stage6 --env-file /path/to/private-stage6.env \
  --override /path/to/private-stage6-ports.yaml --base-url https://localhost:18447
# Отдельная временная schema; queue/card/history p95, 10 sessions:
FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.benchmark_decisions
```

Restart harness проверяет соответствие database port выбранному Compose project, использует собственные временные reviewer accounts, оставляет business history и volumes. По завершении аккаунты отключаются, их сессии отзываются. Он останавливает только worker/Redis выбранного проекта, сохраняет решения через настоящий HTTPS и проверяет однозначность двух конкурирующих отправок. Затем перезапускает PostgreSQL/Redis/backend/frontend, восстанавливает worker и сравнивает ID, полные HTTP карточки, историю и hashes raw/normalization/matching/evidence/Decision. Повтор исходного key после superseding и restart возвращает прежнюю запись.
