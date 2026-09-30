# Forest Keeper — Testing Strategy v0.1

## Цель
Не доверять качеству автора кода, будь это человек или AI. Доверять процессу проверки.

## Слои тестирования

### Unit
Проверка отдельных функций и правил.

### Integration
API ↔ DB, ingestion ↔ normalization, matching ↔ conflict engine, decision ↔ recommendation.

### End-to-End
Полный сценарий:
`source → ingestion → normalization → matching → conflict → recommendation → human decision → Decision Registry → audit`

### Negative / failure
Проверять:
- повреждённые файлы;
- неправильные форматы;
- повторные события;
- недоступность БД/AI;
- частичную обработку;
- неизвестные атрибуты.

### Entity Resolution quality
Измерять precision / recall.
Отдельно контролировать false merge.

### Security
Проверять:
- RBAC;
- обход авторизации;
- секреты;
- невозможность write-back в MVP;
- отсутствие production credentials у AI;
- защиту audit.

### SAST / SCA / secrets
Автоматические проверки кода, зависимостей и секретов.

### DAST
Проверка работающего приложения снаружи.

### Fuzz / property testing
Особенно для ingestion, парсеров и нормализации.

### AI red teaming
Prompt injection, poisoned data, data leakage, forbidden action attempts.

### Mutation testing
Проверять, что тесты действительно обнаруживают намеренно внесённые ошибки.

### Pentest
Независимый pentest перед промышленным пилотом.

## Release gate
Изменение не попадает в релиз при провале обязательных тестов или наличии критической security-проблемы.
