# Forest Keeper — Technical Stack & Module Map v0.1

**Актуально на 25 октября 2026:** Stage 0–7 приняты в `main`. Stage 7 — [PR #28](https://github.com/SergeyRassohin/Forest-Keeper/pull/28), merge `c927af513d29d83bd53b1b6522efccb42b5a1341`, [CI точного merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40079346518). Production embedding provider отключён; synthetic test provider не доказывает промышленное качество. Stage 8 Recommendation Engine начат по [issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29): владелец утвердил численную policy 25 октября; реализация и приёмка в отдельном PR #30 продолжаются. Deterministic Recommendation реализован в PR #30 и проходит приёмку; в main его пока нет. AI/LLM и write-back отсутствуют; #17/#18/#20 открыты.

Статус: обязательная техническая база для MVP. Это целевая карта модулей, не перечень уже реализованных функций. Текущий main: приняты этапы 0–7, включая Human Review, Decision Registry и bounded retrieval; [статус и блокеры](../deployment/review-readiness.md).

## 1. Архитектурный стиль

Для MVP Forest Keeper реализуется как **модульный монолит**.

Это означает:
- один backend-проект;
- одна основная PostgreSQL;
- отдельные логические модули внутри backend;
- без преждевременного дробления на микросервисы;
- границы модулей проектируются так, чтобы при необходимости их можно было вынести позже.

Причина: сейчас важнее быстро получить работающий вертикальный сценарий и сохранить понятную архитектуру, чем построить распределённую систему ради самого факта распределённости.

---

## 2. Backend

### Язык
**Python 3.13**

### Web framework
**FastAPI**

Почему:
- хорошо подходит для REST API;
- нативно работает с типизированными схемами;
- автоматически формирует OpenAPI;
- удобно интегрируется с Python-библиотеками анализа данных, embeddings и локальными AI-моделями.

### Валидация и DTO
**Pydantic v2**

### ORM / работа с БД
**SQLAlchemy 2.x**

### Миграции
**Alembic**

---

## 3. Frontend

Forest Keeper использует браузерный клиент.

### Язык
**TypeScript**

### Framework
**React**

### Сборка
**Vite**

### Работа с API
- обычный REST через HTTPS;
- typed API client;
- на этапе MVP допустимо генерировать типы из OpenAPI backend.

### UI
На MVP не фиксируем тяжёлую корпоративную дизайн-систему.

Требование:
- таблицы;
- фильтры;
- карточка конфликта;
- просмотр исходных значений;
- сравнение источников;
- принятие решения;
- отображение рекомендации и похожих прошлых решений.

---

## 4. Основная база данных

**PostgreSQL**

Используется для:
- пользователей;
- источников;
- импортов;
- канонических сущностей;
- значений;
- конфликтов;
- решений;
- правил;
- шаблонов;
- аудита;
- метаданных лицензии.

### Векторный поиск
**pgvector**

Используется для хранения embeddings и поиска похожих подтверждённых решений.

Для MVP отдельная vector database не нужна.

---

## 5. Файловое хранилище

### MVP
Локальное файловое хранилище внутри серверной инфраструктуры заказчика.

В БД хранится:
- идентификатор файла;
- путь/ключ;
- checksum;
- метаданные;
- provenance.

### В дальнейшем
Интерфейс хранения должен позволить перейти на S3-compatible storage без изменения бизнес-логики.

---

## 6. Фоновые задачи

Для MVP:
**Redis + RQ**.

Используются для:
- импорта больших файлов;
- нормализации;
- matching;
- построения embeddings;
- анализа;
- длительных операций обновления.

Если нагрузка потребует более сложной оркестрации, RQ можно заменить позднее.

---

## 7. AI / Similarity

### Embeddings
MVP baseline: **Qwen/Qwen3-Embedding-0.6B**, 1024 dimensions, локально внутри контура заказчика через `sentence-transformers`; хранение и поиск — PostgreSQL + pgvector.

Точные revision и параметры задаёт `models/model-manifest.yaml`; архитектурные правила — `docs/ai/local-model-v0.1.md`.

Поддержка должна идти через абстракцию `EmbeddingProvider`.

Минимальные реализации:
- `LocalEmbeddingProvider`;
- позднее при необходимости `ExternalEmbeddingProvider`.

### LLM
MVP baseline: **Qwen/Qwen3-8B-GGUF**, `Q4_K_M`, runtime **llama.cpp**, локально внутри контура заказчика. Точные revision и параметры задаёт `models/model-manifest.yaml`.

LLM не является обязательным источником истины.

Он используется для:
- формирования объяснимой рекомендации;
- краткого объяснения найденных прецедентов;
- помощи в предложении нового формального правила;
- анализа текстового контекста.

Backend общается с LLM через интерфейс `LLMProvider`.

Поддерживаемые режимы:
1. локальный LLM внутри инфраструктуры заказчика;
2. внешний approved LLM только если это разрешено политикой ИБ.

Предпочтительный протокол:
**OpenAI-compatible HTTP API** для локальных и внешних провайдеров, если это возможно.

Это позволяет менять конкретную модель без переписывания Recommendation Engine.

---

## 8. Лицензирование

### На стороне клиента
Модуль `License Service` внутри backend.

Функции:
- загрузка `forestkeeper.license`;
- проверка цифровой подписи;
- проверка срока;
- проверка edition;
- проверка разрешённых модулей;
- graceful/read-only поведение после истечения лицензии по правилам проекта.

### На стороне поставщика
Отдельное приложение:
**FK License Generator**.

Оно не входит в клиентский runtime Forest Keeper.

---

## 9. Обновления

Модуль `Update Service`.

Для MVP:
- проверка версии;
- проверка подписи пакета;
- backup;
- миграции БД;
- health check после обновления;
- rollback при ошибке.

Поддержка:
- online update;
- offline signed package.

---

## 10. Аутентификация и авторизация

### MVP
- локальные пользователи FK;
- пароль хранится только как secure hash;
- server-side session with Secure/HttpOnly/SameSite=Strict cookie only; bearer login is outside MVP by the 2026-10-19 decision;
- RBAC.

Роли минимум:
- ADMIN;
- DATA_OWNER;
- REVIEWER;
- VIEWER.

Архитектура должна позволять позднее подключить:
- LDAP;
- Active Directory;
- OIDC/SAML.

Но эти интеграции не блокируют MVP.

---

## 11. Логирование и аудит

### Технические логи
Стандартный Python logging со структурированным JSON-форматом.

### Бизнес-аудит
Отдельный `AuditService` и таблица аудита.

Обязательно логируются:
- импорт;
- запуск анализа;
- изменение шаблона;
- изменение правила;
- решение человека;
- принятие/отклонение recommendation/rule suggestion;
- лицензионные события;
- административные действия.

---

## 12. Тестирование

### Backend
- `pytest`;
- unit tests;
- integration tests;
- API tests.

### Frontend
- `Vitest`;
- React Testing Library.

### End-to-end
- `Playwright`.

Первый обязательный E2E-тест:

**загрузить два файла → запустить анализ → получить конфликт → принять решение → загрузить похожий новый случай → получить рекомендацию на основе прошлого решения.**

Если этот сценарий не работает автоматически, MVP не считается готовым.

---

## 13. Контейнеризация и локальная разработка

### Разработка
**Docker Compose**

Минимальные контейнеры:
- `backend`;
- `frontend`;
- `postgres`;
- `redis`;
- при необходимости локальный AI/embedding service.

### Production
Контейнеры могут использоваться как внутренняя реализация, но заказчик получает обычный корпоративный installer.

Пользователь заказчика не должен вручную собирать Docker Compose.

---

## 14. Структура репозитория

Рекомендуемая структура monorepo:

```text
/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ auth/
│  │  ├─ sources/
│  │  ├─ ingestion/
│  │  ├─ normalization/
│  │  ├─ canonical/
│  │  ├─ matching/
│  │  ├─ conflicts/
│  │  ├─ decisions/
│  │  ├─ recommendations/
│  │  ├─ rules/
│  │  ├─ templates/
│  │  ├─ ai/
│  │  ├─ licensing/
│  │  ├─ updates/
│  │  ├─ audit/
│  │  └─ common/
│  ├─ migrations/
│  └─ tests/
│
├─ frontend/
│  ├─ src/
│  └─ tests/
│
├─ license-generator/
│
├─ docs/
├─ models/
│  ├─ model-manifest.yaml
│  └─ README.md
├─ deploy/
│  ├─ docker/
│  └─ installer/
│
├─ scripts/
└─ tests/
   └─ e2e/
```

---

## 15. Карта backend-модулей

### `auth`
Пользователи, роли, доступ.

### `sources`
Описание источников данных.

### `ingestion`
Приём XLSX/CSV/XML/JSON, создание ImportBatch и RawRecord.

### `normalization`
Приведение форматов без уничтожения исходных значений.

### `canonical`
Канонические сущности и значения.

### `matching`
Поиск кандидатов на совпадение:
- exact;
- rules;
- fuzzy;
- embeddings;
- hybrid.

### `conflicts`
Выявление конфликтов и формирование карточки для Human Review.

### `decisions`
Decision Registry.

Хранит:
- что решил человек;
- в каком контексте;
- когда;
- кто;
- какое значение было подтверждено.

### `recommendations`
Собирает:
- текущий конфликт;
- действующие правила;
- похожие решения;
- similarity score;
- AI explanation.

Возвращает рекомендацию, но не меняет данные автоматически.

### `rules`
Формальные правила клиента.

### `templates`
Базовый шаблон FK и текущая конфигурация клиента.

### `ai`
Абстракции:
- `EmbeddingProvider`;
- `LLMProvider`.

AI не содержит бизнес-решений и не является хранилищем памяти.

### `licensing`
Проверка лицензии.

### `updates`
Обновления продукта.

### `audit`
Неизменяемая история значимых действий.

### `common`
Только общие технические элементы:
- конфигурация;
- DB session;
- базовые ошибки;
- shared DTO;
- security helpers.

Бизнес-логика не должна сваливаться в `common`.

---

## 16. Зависимости между модулями

Основной поток:

```text
sources
  ↓
ingestion
  ↓
normalization
  ↓
canonical
  ↓
matching
  ↓
conflicts
  ↓
recommendations
  ↓
human review
  ↓
decisions

rules/templates ──→ conflicts/recommendations
historical decisions ──→ similarity ──→ recommendations
```

Дополнительные зависимости:

```text
recommendations → decisions
recommendations → rules
recommendations → ai
recommendations → matching/similarity

all business modules → audit

api → application modules
application modules → database
```

Запрещено:
- `ai` напрямую менять `decisions`;
- `ai` напрямую менять `rules`;
- `ai` писать в системы заказчика;
- frontend обращаться напрямую в PostgreSQL;
- адаптеры источников менять production-системы в MVP.

---

## 17. Что не делаем в первой версии

Не добавляем без реальной необходимости:
- Kubernetes;
- Kafka;
- отдельную vector DB;
- десятки микросервисов;
- GraphQL;
- собственную нейросеть;
- сложную event-driven архитектуру;
- service mesh;
- distributed tracing уровня крупного облака.

Это всё может понадобиться позже. Пока оно в основном помогает красиво потратить месяц и ничего не показать пользователю.

---

## 18. Минимальный технический состав первого вертикального MVP

Для первой работающей версии Codex должен создать:

1. FastAPI backend.
2. PostgreSQL + Alembic migrations.
3. Redis + RQ.
4. React/TypeScript frontend.
5. Импорт XLSX/CSV/XML минимум из двух источников, включая выгрузку 1С XML как целевой сценарий MVP.
6. RawRecord + provenance.
7. Нормализацию.
8. Matching.
9. Conflict.
10. Human Review.
11. Decision Registry.
12. pgvector similarity по прошлым решениям.
13. Recommendation Engine.
14. Локальный AI provider по baseline `docs/ai/local-model-v0.1.md` + `models/model-manifest.yaml`.
15. Audit.
16. Базовые API и E2E-тест главного сценария.

После выполнения этого списка у Forest Keeper появится не только архитектура, но и работающий позвоночник продукта.
