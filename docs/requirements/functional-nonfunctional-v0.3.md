# Forest Keeper — функциональные и нефункциональные требования v0.3

Статус: обязательные требования MVP.  
v0.3 заменяет v0.2 для разработки.

## 1. Назначение

Forest Keeper — интеллектуальный слой над корпоративными системами, который получает разрешённые данные, сопоставляет сущности, выявляет конфликты и аномалии, формирует рекомендации, передаёт неоднозначные случаи человеку и сохраняет решения.

Численные значения в разделе NFR являются **инженерным baseline MVP**, а не договорным SLA заказчику. После benchmark первого пилота они пересматриваются отдельным проектным решением.

## 2. Ключевые функциональные требования

### FK-FR-ING-001 — Источники
Поддержать получение данных из файловых и корпоративных источников. Для MVP: XML/CSV/XLSX и выгрузки из 1С.

### FK-FR-RAW-001 — Сохранение исходных данных
Сохранять исходные данные без изменения и сохранять provenance.

### FK-FR-NORM-001 — Нормализация
Преобразовывать значения в единое внутреннее представление для сравнения. Нормализованное значение не является эталонным.

### FK-FR-MD-001 — Преднастроенные мастер-данные
FK поставляется с преднастроенным представлением о мастер-данных для поддерживаемых доменов.

### FK-FR-MD-002 — Настройка под заказчика
Структура мастер-данных, обязательность, форматы, единицы, справочники и правила могут настраиваться под предприятие.

### FK-FR-AUTH-001 — Authoritative Source
Авторитетный источник может быть определён на уровне домена, сущности или атрибута.

### FK-FR-AUTH-002 — NOT_DEFINED
Отсутствие назначенного авторитетного источника является допустимым состоянием.

### FK-FR-ER-001 — Entity Resolution
Определять, относятся ли записи из разных источников к одной бизнес-сущности.

### FK-FR-ER-002 — Объяснимость
Для сопоставления сохранять основания и confidence.

### FK-FR-CONF-001 — Конфликты
Выявлять расхождения между сопоставленными сущностями и классифицировать проблему как нарушение правила, конфликт или вероятную аномалию.

### FK-FR-BASIS-001 — Основание оценки
Для каждой проблемы хранить Basis: правило, стандарт, Authoritative Source, межсистемный конфликт, подтверждённое правило или AI-pattern.

### FK-FR-HITL-001 — Human Review
Неоднозначные случаи передавать человеку.

### FK-FR-DEC-001 — Decision Registry
Сохранять подтверждённые решения людей со всем контекстом: объект, атрибут, значения источников, выбранный результат, пользователь, время, причина.

### FK-FR-REC-001 — Рекомендации
Для нового похожего случая искать подтверждённые решения и формировать объяснимую рекомендацию.

### FK-FR-AI-001 — AI не является памятью
Знания предприятия хранятся структурированно в Rules, mappings, Decision Registry, canonical/master model и Audit.

### FK-FR-AUD-001 — Audit
Восстанавливать цепочку Source → Import → Raw → Analysis → Recommendation → Decision → Result.

### FK-FR-UI-001 — Главный экран
Главная страница показывает состояние информационной среды предприятия, а не обычный список назначенных задач.

## 3. Граница MVP 0.1

MVP:
- читает данные заказчика;
- сохраняет их внутри FK;
- не пишет обратно в 1С/CRM/Excel;
- не принимает критические решения автоматически;
- показывает конфликты и рекомендации;
- сохраняет решение человека;
- использует подтверждённые решения как опыт для рекомендаций;
- работает через Web Client;
- поддерживает локальный/offline контур.

## 4. Нефункциональные требования

### 4.1 Security

#### FK-NFR-SEC-001 — Read-only source boundary
MVP не имеет прав изменения исходных production-систем.

#### FK-NFR-SEC-002 — Least privilege
Компоненты и пользователи получают только минимально необходимые права.

#### FK-NFR-SEC-003 — AI isolation
AI/LLM не получает production credentials и не пишет напрямую в системы заказчика.

#### FK-NFR-SEC-004 — RBAC
Backend обязан проверять права независимо от frontend. Канонический источник прав MVP:  
`docs/security/access-control-matrix-v0.1.xlsx`.

#### FK-NFR-SEC-005 — Transport
Пользовательский доступ к FK Server выполняется по HTTPS. Секреты и пароли не передаются в открытом виде.

#### FK-NFR-SEC-006 — Password storage
Локальные пароли хранятся только в виде современного адаптивного password hash. Plaintext-пароли в БД, логах и конфигурации запрещены.

#### FK-NFR-SEC-007 — Dependency/security checks
CI обязан выполнять dependency/vulnerability scan. Известные Critical-уязвимости блокируют release build до явного документированного исключения.

### 4.2 Audit and traceability

#### FK-NFR-AUD-001 — Неизменяемость аудита
Обычный пользователь не может переписывать или удалять историю значимых действий.

#### FK-NFR-AUD-002 — Correlation
Технические логи фоновых операций должны содержать correlation/request/job identifier, чтобы связать API-запрос, background job и AuditEvent.

#### FK-NFR-AUD-003 — UTC storage
Системные timestamps хранятся однозначно с timezone/UTC; UI может показывать локальное время пользователя.

### 4.3 Explainability and AI

#### FK-NFR-EXP-001 — Explainability
Любая Recommendation должна иметь объяснимое основание: Rules/Basis, похожие Decisions и/или Authoritative Source.

#### FK-NFR-MOD-001 — Заменяемость AI
Смена LLM/embedding-модели не должна уничтожать накопленные Decisions, Rules и Audit.

#### FK-NFR-AI-002 — Graceful degradation
Недоступность LLM не должна блокировать просмотр Conflict, Decision Registry и детерминированную rule/similarity часть сценария.

### 4.4 Reliability and recovery

#### FK-NFR-REL-001 — Идемпотентность
Повторная обработка одного и того же файла/события не должна создавать неуправляемые дубли. Для файлов используется checksum и идентификатор ImportBatch.

#### FK-NFR-REL-002 — Partial import failure
Ошибка отдельной записи не должна уничтожать успешно обработанные записи пакета. Используется состояние COMPLETED_WITH_ERRORS.

#### FK-NFR-REL-003 — Healthcheck
Backend обязан иметь health endpoint, проверяющий как минимум готовность API и соединение с обязательными инфраструктурными зависимостями.

#### FK-NFR-REL-004 — Recovery baseline
После обычного перезапуска контейнеров данные PostgreSQL и файлового хранилища сохраняются. В E2E/installation test должен быть сценарий restart → healthcheck → продолжение работы.

#### FK-NFR-REL-005 — Update rollback
Тестовое обновление обязано проверять backup, migration, healthcheck и rollback согласно Update Service spec.

### 4.5 Performance baseline MVP

Эти числа используются как **development acceptance targets** на эталонном тестовом стенде проекта. Они не являются SLA первого заказчика.

#### FK-NFR-PER-001 — Интерактивный API
Для обычных metadata/list/detail endpoint без запуска тяжёлой обработки: p95 ≤ 1 секунда при 10 одновременных пользовательских сессиях на тестовом стенде.

#### FK-NFR-PER-002 — Conflict card
Карточка Conflict без ожидания нового LLM generation должна отдавать основные данные p95 ≤ 2 секунд.

#### FK-NFR-PER-003 — Health
`/api/v1/health` должен отвечать ≤ 1 секунды при исправной инфраструктуре.

#### FK-NFR-PER-004 — Background work
Импорт, normalization, matching, embeddings и длительный анализ не должны удерживать HTTP-запрос до завершения. Они выполняются background job с возвращаемым статусом.

### 4.6 Capacity test profile

#### FK-NFR-CAP-001 — Базовый профиль импорта
До первого пилотного benchmark обязательный тестовый профиль MVP:
- не менее 100 000 записей в одном source dataset;
- два source dataset в одном полном E2E-сценарии;
- не менее 30 атрибутов на запись в синтетическом benchmark;
- входной файл/пакет до 100 MB.

Это не заявленный продуктовый максимум. Если пилот требует больше, профиль повышается отдельным решением и benchmark.

#### FK-NFR-CAP-002 — История решений
Similarity test должен проверять минимум 10 000 сохранённых Decisions без изменения бизнес-контракта API.

### 4.7 Compatibility

#### FK-NFR-COMP-001 — Browsers
Web Client MVP должен работать в актуальных desktop-версиях Chrome, Edge и Firefox. Поддержка мобильных браузеров не является обязательной для MVP.

#### FK-NFR-COMP-002 — Offline
Основной пользовательский сценарий должен работать в закрытом контуре без доступа в Интернет при наличии локальных зависимостей и моделей.

### 4.8 Testability and CI quality gates

#### FK-NFR-TEST-001 — Critical path
Главный E2E обязателен:
`два источника → import → normalization → matching → conflict → recommendation → human decision → Decision Registry → похожий следующий случай → recommendation на основе прошлого Decision`.

#### FK-NFR-TEST-002 — Test layers
Обязательны:
- backend unit tests;
- backend integration/API tests;
- frontend component tests;
- Playwright E2E для критического пользовательского пути.

#### FK-NFR-TEST-003 — State machines
Для lifecycle-объектов обязательны тесты разрешённых и критических запрещённых переходов.

#### FK-NFR-TEST-004 — RBAC
Для каждой permission из Access Control Matrix должен существовать backend authorization test минимум на разрешённый и запрещённый сценарий.

#### FK-NFR-TEST-005 — CI gates
Merge/release build блокируется, если не проходят:
- automated tests;
- lint/format checks;
- type/static checks, предусмотренные стеком;
- migration validation;
- build frontend/backend;
- Critical dependency security scan.

Порог общего code coverage не используется как единственный критерий качества. Критические модули auth, decisions, conflicts, licensing, state transitions и permission checks должны иметь прямые автоматические тесты независимо от суммарного процента покрытия.

### 4.9 Observability

#### FK-NFR-OBS-001 — Structured logs
Backend пишет структурированные технические логи, пригодные для машинного поиска.

#### FK-NFR-OBS-002 — Error visibility
Background job failure должен быть виден в ImportBatch/AnalysisRun status и техническом логе; ошибка не должна исчезать только в stdout контейнера.

#### FK-NFR-OBS-003 — Audit vs debug logs
Audit и технические debug/runtime logs являются разными механизмами. Бизнес-аудит не зависит от уровня технического логирования.

### 4.10 Deployment constraints

#### FK-NFR-DEP-001 — Deployment
MVP ориентирован на контейнеризованное on-prem/private развёртывание.

#### FK-NFR-DEP-002 — Installer boundary
Заказчик получает обычный installer/setup flow; Docker Compose не должен быть обязательным пользовательским интерфейсом установки.

#### FK-NFR-DEP-003 — Reproducibility
Чистый checkout repository должен подниматься документированной локальной последовательностью с применением migrations и запуском automated smoke test.

## 5. Что измеряется после первого pilot benchmark

До production SLA остаются отдельными проектными решениями:
- контрактная доступность;
- RPO/RTO заказчика;
- production concurrency;
- максимальный поддерживаемый объём одного импорта;
- срок хранения raw/audit/log data;
- HA topology;
- точные p95/p99 production latency targets.

Отсутствие этих коммерческих/production параметров **не разрешает Codex игнорировать baseline MVP из раздела 4**.
