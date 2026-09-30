# Forest Keeper — Update and Release Model v0.1

## 1. Цель

Forest Keeper должен поддерживать безопасное обновление как в online, так и в полностью закрытом контуре.

## 2. Update Service

Update Service:
- проверяет пакет;
- проверяет подпись;
- проверяет совместимость;
- создаёт backup;
- обновляет контейнеры/компоненты;
- применяет миграции БД;
- запускает health check;
- выполняет rollback при неуспешном обновлении.

## 3. Offline update package

Пример:
`ForestKeeper_Update_1.4.2.pkg`

Пакет содержит:
- новые образы/дистрибутивы;
- DB migrations;
- конфигурационные изменения;
- manifest;
- changelog;
- контрольные суммы;
- цифровую подпись поставщика.

## 4. Процесс

```
получить update package
→ verify signature
→ compatibility check
→ backup
→ stop affected services
→ deploy new version
→ DB migration
→ start
→ health check
→ success OR rollback
```

## 5. Rollback

Rollback должен быть предусмотрен архитектурно.

Минимум:
- backup DB;
- previous application/container version;
- versioned configuration;
- controlled migration strategy.

## 6. Online update

Опционально:

```
FK Update Service → HTTPS → Forest Keeper Update Server
```

Для закрытых предприятий online connectivity не требуется.

## 7. Версионирование

Рекомендуется Semantic Versioning:
- 0.x — prototype/pre-release;
- 1.0.0 — первый стабильный production release;
- patch — исправления;
- minor — совместимая новая функциональность;
- major — потенциально несовместимые изменения.

Каждый релиз получает Git tag и changelog.
