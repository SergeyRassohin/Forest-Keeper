# Forest Keeper

Forest Keeper помогает сравнить данные из разных корпоративных систем и разобрать расхождения. Например, одна и та же деталь может иметь разные названия, единицы измерения или значения в 1С и Excel. Продукт сохраняет исходные записи, показывает основания сравнения и оставляет спорное решение человеку.

Целевой результат: подтверждённое решение сохраняется в истории и помогает предложить решение следующего похожего случая. Это направление продукта; доступность функций текущей версии указана ниже.

Forest Keeper разворачивается внутри инфраструктуры заказчика. Основной интерфейс — браузер. Прототип читает выгрузки и записывает результаты только в собственное хранилище; изменения обратно в 1С/ERP не отправляются. Нормализация не устанавливает «истинное» значение. Локальная Qwen объясняет переданный контекст; память продукта — структурированные решения, правила и аудит.

## Внешнему проверяющему: начните здесь

**[Пошаговая инструкция установки и проверки](docs/deployment/external-review-quickstart.md)** объясняет подготовку машины, первый вход, загрузку примеров и ожидаемые результаты. Знание архитектуры Forest Keeper не требуется.

Контрольная дата внешней проверки — **24 октября 2026**. Это цель, а не заявление о готовности полного MVP.

## Схемы и презентация

- актуальная блок-схема бизнес-процесса Forest Keeper и GitHub Actions CI: [workflow overview](docs/architecture/workflow-overview.md);
- актуальная презентация продукта и состояния MVP: [presentation v0.1](docs/marketing/presentation-v0.1.md).

## Что доступно в проверяемой версии

Проверяемая версия — `main`, в которой приняты этапы 0–4. Matching объединён через [PR #15](https://github.com/SergeyRassohin/Forest-Keeper/pull/15), merge `bea0d55c92540744657feac863084cde131a7f43`; [CI merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39595762080). В main также включены изменения PR #19. Инструкция получает основную ветку; сохраняйте точный SHA проверки.

| Возможность | Статус |
| --- | --- |
| Вход, роли, создание пользователей | Реализовано, этап 1 принят |
| CSV/XLSX/XML: импорт, оригинал, исходные записи и происхождение | Реализовано, этап 2 принят |
| Нормализация по объявленному профилю, качество значений, история правил | Реализовано, этап 3 принят |
| Matching: совпадение / требует проверки / не совпадает | Реализовано в main, этап 4 принят; независимый retest и CI merge commit PASS |
| Conflict Engine | ТЗ зафиксировано в [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21); runtime ещё не реализован в main |
| Human Review с сохранением Decision | Не реализовано в main; этапы 6–7 после Conflict Engine |
| Поиск прошлого Decision, рекомендации, AI inference | Не реализовано в main |
| Получение и проверка pinned Qwen artifacts | [Команды и точные ссылки](docs/ai/model-downloads.md); это подготовка файлов, без запуска AI |
| Корпоративный установщик, лицензирование, Update Service | Последующие этапы |

Этап 3 принят через [PR #13](https://github.com/SergeyRassohin/Forest-Keeper/pull/13), merge `6a494534a49960b79fdf64e5e2b8436c32011688`; [CI merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39452965438). Этап 4 принят через PR #15. Следующий отдельный этап — **Stage 5 Conflict Engine**, полное ТЗ и критерии приёмки находятся в [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21). Полный путь «свой файл → конфликт → Decision → похожий случай → рекомендация» пока **заблокирован отсутствующими модулями**, см. [критерии готовности](docs/deployment/review-readiness.md). Зелёный health означает готовность инфраструктуры, а не наличие всех бизнес-функций.

## Что можно проверить сейчас

1. Развернуть приложение, создать администратора и войти через браузер.
2. Создать два источника и загрузить CSV/XLSX/XML.
3. Проверить исходные записи, позиции, SHA-256 файла и нормализацию.
4. На двух [синтетических наборах для matching](tests/data/matching/README.md) получить три статуса сопоставления, открыть основания и подтвердить либо отклонить сомнительную пару с причиной под ролью REVIEWER. Это проверка идентичности записей; сохранение бизнес-решения по конфликту относится к следующим этапам.
5. Перезапустить систему и убедиться, что пакеты и результаты сохранились.
6. Проверить импорт своего файла с учётом [поддерживаемых форматов](docs/development/import.md). Для нормализации нужен профиль именно его полей; произвольные колонки автоматически не интерпретируются.

Есть [пример на открытых данных USGS](tests/data/external-review/README.md) и отдельный профиль для него. Примеры демонстрируют обработку, а не качество промышленного Entity Resolution. Первый промышленный pilot domain остаётся отдельным решением.

Дополнительно: [разработка и тесты](docs/development/local-development.md), [развёртывание на сервере](docs/deployment/server-installation-v0.1.md), [состояние этапов](docs/development/mvp-progress.md), [архитектура](docs/architecture/architecture-v0.2.md).

## Как работать

- **ChatGPT** — обсуждение идеи, продукта, архитектуры, требований, интерфейса, безопасности и принятие решений.
- **GitHub** — зафиксированные решения, документация, код, история версий и артефакты проекта.
- **Codex** — разработка и изменение файлов/кода внутри этого репозитория.

Правило: важная договорённость считается частью проекта только после фиксации в GitHub.

## Инженерные документы

1. [Правила разработки](AGENTS.md)
2. [Контекст продукта](docs/project-context.md)
3. [Журнал решений](docs/decisions/decision-log.md)
4. [Product Roadmap — направление продукта](docs/product-roadmap-v0.1.md)
5. [План реализации MVP](docs/development/mvp-development-plan-v0.1.md)
6. [Архитектура](docs/architecture/architecture-v0.2.md)
7. [Каноническая модель данных](docs/data-model/data-model-v0.2.md)
8. [API-контракт](docs/api/api-contract-v0.1.md)
9. [Стек и модули](docs/architecture/technical-stack-and-module-map-v0.1.md)
10. [Жизненные циклы](docs/development/object-lifecycles-v0.1.md)
11. [Матрица доступа](docs/security/access-control-matrix-v0.1.xlsx)
12. [Функциональные и нефункциональные требования](docs/requirements/functional-nonfunctional-v0.3.md)
13. [Рабочие процессы](docs/workflows/workflows-v0.2.md)
14. [Безопасность](docs/security/security-v0.1.md)
15. [Стратегия тестирования](docs/testing/testing-strategy-v0.1.md)
16. [AI baseline](docs/ai/local-model-v0.1.md)
17. [Model manifest](models/model-manifest.yaml)
18. [Лицензирование](docs/licensing/licensing-v0.1.md)
19. [Обновления](docs/deployment/update-model-v0.1.md)
20. [Блок-схема процесса и CI](docs/architecture/workflow-overview.md)
21. [Презентация продукта](docs/marketing/presentation-v0.1.md)

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
- `docs/marketing/` — позиционирование, презентация и материалы
- `docs/development/` — правила разработки, MVP-план и жизненные циклы объектов
- `docs/api/` — API-контракты
- `docs/data-model/` — каноническая модель данных; XLSX v0.1 сохранён как исторический черновик
- `docs/licensing/` — лицензирование и License Generator
- `docs/deployment/` — установка и обновления
- `docs/ai/` — AI/embedding baseline и правила интеграции
- `models/` — manifest и конфигурация моделей без весовых файлов

## Stage 5: реализация в отдельном PR

Ветка `codex/stage5-conflict-engine` содержит [Conflict Engine](docs/development/conflicts.md): persisted OPEN conflicts, async analysis, API и Web list/detail с immutable evidence. Это проверяемая реализация PR, а не принятый main. [Независимый runtime/security/product-intent retest](docs/testing/reports/stage5-conflicts-independent-2026-10-22.md) PASS: 679 тестов, security/dependencies, quality, capacity 100/1k/10k/100k, production smoke и restart. Блокирующих замечаний нет. Финальный HEAD/CI — в PR #22; до отдельного разрешения владельца merge и принятие в main не выполняются. Полный MVP #18/#20 остаётся незавершённым.
