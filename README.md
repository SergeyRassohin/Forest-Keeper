# Forest Keeper

Этот репозиторий — единый инженерный источник истины по проекту Forest Keeper.

## Разработка MVP

Запускаемый каркас и команды проверки: [локальная разработка](docs/development/local-development.md).
Этап 0 добавляет backend, Web Client, PostgreSQL/pgvector, Redis/RQ и HTTPS-контур разработки.
Этап 1 добавляет [локальный вход, пользователей и RBAC](docs/development/authentication.md).
Этап 2 добавляет [источники и импорт CSV/XLSX/XML](docs/development/import.md) через браузер с сохранением оригиналов, raw-записей и provenance.
Нормализация, matching, Human Review и рекомендации относятся к следующим этапам.

## Как работать

- **ChatGPT** — обсуждение идеи, продукта, архитектуры, требований, интерфейса, безопасности и принятие решений.
- **GitHub** — зафиксированные решения, документация, код, история версий и артефакты проекта.
- **Codex** — разработка и изменение файлов/кода внутри этого репозитория.

Правило: важная договорённость считается частью проекта только после фиксации в GitHub.

## Что читать сначала

1. `AGENTS.md`
2. `docs/project-context.md`
3. `docs/decisions/decision-log.md`
4. `docs/architecture/architecture-v0.2.md`
5. `docs/data-model/data-model-v0.2.md`
6. `docs/api/api-contract-v0.1.md`
7. `docs/architecture/technical-stack-and-module-map-v0.1.md`
8. `docs/development/mvp-development-plan-v0.1.md`
9. `docs/development/object-lifecycles-v0.1.md`
10. `docs/security/access-control-matrix-v0.1.xlsx`
11. `docs/requirements/functional-nonfunctional-v0.3.md`
12. `docs/workflows/workflows-v0.2.md`
13. `docs/security/security-v0.1.md`
14. `docs/testing/testing-strategy-v0.1.md`
15. `docs/ai/local-model-v0.1.md`
16. `models/model-manifest.yaml`
17. `docs/licensing/licensing-v0.1.md`
18. `docs/deployment/server-installation-v0.1.md`
19. `docs/deployment/update-model-v0.1.md`

## Структура

- `docs/requirements/` — функциональные и нефункциональные требования
- `docs/architecture/` — архитектура
- `docs/workflows/` — рабочие процессы
- `docs/interface/` — интерфейс
- `docs/security/` — безопасность и матрица доступа
- `docs/testing/` — тестирование
- `docs/decisions/` — журнал решений
- `docs/sessions/` — краткие итоги обсуждений
- `docs/site/` — сайт / Project Portal
- `docs/marketing/` — позиционирование и материалы
- `docs/development/` — правила разработки, MVP-план и жизненные циклы объектов
- `docs/api/` — API-контракты
- `docs/data-model/` — каноническая модель данных; XLSX v0.1 сохранён как исторический черновик
- `docs/licensing/` — лицензирование и License Generator
- `docs/deployment/` — установка и обновления
- `docs/ai/` — AI/embedding baseline и правила интеграции
- `models/` — manifest и конфигурация моделей без весовых файлов
