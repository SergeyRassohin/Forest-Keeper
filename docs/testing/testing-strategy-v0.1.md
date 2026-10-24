# Forest Keeper — Testing Strategy v0.1

## Цель
Не доверять качеству автора кода, будь это человек или AI. Доверять процессу проверки.

Численные MVP acceptance targets берутся из `docs/requirements/functional-nonfunctional-v0.3.md`.

## Слои тестирования

### Unit
Проверка отдельных функций и правил.

### Integration
API ↔ DB, ingestion ↔ normalization, matching ↔ conflict engine, decision ↔ recommendation.

### End-to-End
Полный сценарий:
`source → ingestion → normalization → matching → conflict → recommendation → human decision → Decision Registry → audit → similar future recommendation`

### Negative / failure
Проверять:
- повреждённые файлы;
- неправильные форматы;
- повторные события;
- недоступность БД/AI;
- частичную обработку;
- неизвестные атрибуты;
- restart сервисов;
- update rollback.

### State models
Для каждого lifecycle-объекта:
- разрешённые переходы;
- критические запрещённые переходы;
- отсутствие изменения статуса при ошибке операции;
- AuditEvent на значимый переход.

### RBAC
Канонический источник permission: `docs/security/access-control-matrix-v0.1.xlsx`.

Для каждой permission:
- минимум один разрешённый backend/API сценарий;
- минимум один запрещённый сценарий;
- frontend не считается механизмом безопасности.

### Entity Resolution quality
Измерять precision / recall.
Отдельно контролировать false merge.

### Performance / capacity
Использовать baseline из NFR v0.3:
- интерактивный API;
- Conflict card;
- healthcheck;
- 100k-record import profile;
- Decision Registry similarity profile.

### Security
Проверять:
- RBAC;
- обход авторизации;
- секреты;
- невозможность write-back в MVP;
- отсутствие production credentials у AI;
- защиту Audit.

### SAST / SCA / secrets
Автоматические проверки кода, зависимостей и секретов.

### DAST
Проверка работающего приложения снаружи.

### Fuzz / property testing
Особенно для ingestion, парсеров и нормализации.

### AI red teaming
Prompt injection, poisoned data, data leakage, forbidden action attempts.

### Mutation testing
Использовать точечно для критичных правил, когда базовый набор unit/integration tests стабилен.

### Pentest
Независимый pentest перед промышленным пилотом.

## Release gate
Изменение не попадает в релиз при провале обязательных тестов, migration validation, build/lint/type checks или наличии Critical security-проблемы без документированного исключения.

## Stage 7 acceptance

Issue #27 requires actual import→Decision→new Conflict→pgvector retrieval, unrelated/below-threshold cases, all compatibility fields, scope/IDOR, unavailable Registry/review, snapshot concurrency, bounded query abuse, backfill retry/checkpoint/restart, dual versions, migration guards and all Stage1–6 regressions. `tests.benchmark_similarity` uses 100/1k/10k actual persisted synthetic Decision rows with guards enabled, not Conflict queue counts. Browser/gallery exercises real HTTPS plus Axe/five viewports. Independent review and exact-final-HEAD CI precede READY TO MERGE; no merge without owner instruction. [Policies](../development/similarity-retrieval.md).
