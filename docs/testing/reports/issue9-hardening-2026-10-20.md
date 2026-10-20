# Issue #9: worker readiness и production hardening

Дата: 2026-10-20. База: main `573b421`. Изолированная ветка
`fix/worker-production-hardening`; изменения Stage 2 из PR #8 сюда не включены.

## Результаты локальной проверки

| Проверка | Результат |
| --- | --- |
| Ruff check/format, mypy, frontend lint/build/e2e typecheck | PASS |
| Backend unit | 23 PASS, включая 15 новых проверок health/file secrets |
| Backend integration PostgreSQL/Redis, миграция 0002 | 222 PASS |
| Frontend unit | 9 PASS |
| Browser Chromium HTTPS | 6 PASS |
| Bandit и TypeScript security ESLint | PASS |
| pip-audit и npm audit | PASS, известных уязвимостей не найдено |
| Gitleaks history + tracked tree | PASS, утечек не найдено |
| Негативные security fixtures B602 / eval / github-pat | Все три обнаружены |
| Production Compose config + реальные контейнеры | PASS |

Всего 260 unit/integration/browser tests. Проверки dev выполнены отдельным project
`fk-issue9-dev` с переопределёнными localhost-портами; существующее окружение Stage 2
и его данные не изменялись. Для сборки использован существующий proxy CA adapter.

## Production smoke

`scripts/check-production.py` запускался на образах `fk-issue9-dev-backend` и
`fk-issue9-dev-frontend` в одноразовом случайном project с синтетическими credentials.
Проверено:

- внешний HTTPS health с проверкой доверия сертификату;
- запуск всех сервисов non-root, read-only rootfs, CPU/memory limits, cap drop;
- отказ записи в `/app`, разрешённая временная запись в `/tmp`;
- выполнение реального технического RQ задания `operator.add(2, 3)`;
- healthy → SIGSTOP собственного worker и старение его heartbeat → probe failure
  и фактический Docker unhealthy → stop → start → healthy;
- сохранность синтетических PostgreSQL/Redis значений после restart;
- отсутствие значений DB password/DSN в Compose render, Config.Env и логах;
- удаление только тестовых контейнеров и volumes после проверки.

Первый runtime прогон выявил ошибки прав чтения nginx config/TLS fixture при non-root.
Config включён в image с явными правами, TLS directory доступен nginx, тестовые cert/key
читаются container UID внутри закрытого временного каталога. Повторный полный smoke — PASS.
Последняя правка обработчика ошибки probe (`healthy = False` вместо пустого `except`)
проверена unit/SAST; CI повторяет smoke с окончательным исходным кодом.

## Независимая проверка и пределы

Отдельный reviewer выполнил read-only review probe, RQ heartbeat timing, Settings,
Compose/nginx и smoke, самостоятельно повторил 15 новых unit tests и проверил rendered
Compose: замечаний в проверенном diff не найдено. Полный runtime smoke выполнил основной агент.

Это закрытие технического долга №9, а не приёмка всего приложения для production.
Compose unhealthy требует мониторинга/реакции оператора; автоматический restart зависшего
процесса не реализован. Контейнерные секреты доступны Docker administrator.
Реальные файловые права, backups/restore, ротация, ресурсы и настройки ядра проверяются
на целевом сервере по [инструкции](../../deployment/production-profile.md).

CI запускает все gates и production smoke на каждом push/pull request. Результат конкретного
commit следует проверять в GitHub Checks соответствующего PR; локальные PASS не заменяют CI.
