# Этап 1: Authentication + RBAC

Реализованы локальный вход/выход, User/UserRole, серверные сессии, backend permissions и административное создание пользователя. Используются только VIEWER, REVIEWER, DATA_OWNER, ADMIN и 39 permissions из `docs/security/access-control-matrix-v0.1.xlsx`. Runtime-каталог `backend/app/auth/permissions.json` содержит SHA-256 матрицы; тест независимо читает XLSX и сравнивает все значения. При изменении матрицы явно синхронизируйте каталог и повторите проверки.

## Первый администратор

После применения `0002_auth` и запуска Compose выполните из корня:

```bash
docker compose exec backend python -m app.auth.bootstrap --login admin --full-name "Администратор"
```

Пароль вводится скрыто через getpass, не передаётся в argv и не имеет значения по умолчанию. Bootstrap возможен только в пустой таблице пользователей и сериализуется PostgreSQL table lock; существующие аккаунты не изменяются. Создаётся только ADMIN. Через Web Client он может создавать пользователей и назначать фиксированные роли. Для бизнес-решений отдельно нужны REVIEWER/DATA_OWNER — ADMIN их не наследует. Self-registration и пользовательские роли не реализованы.

Для CLI на хосте экспортируйте `.env`, затем из backend вызовите `uv run --frozen python -m app.auth.bootstrap` с теми же аргументами. `--password-stdin` предназначен для безопасного автоматизированного ввода; не вставляйте реальный пароль в команду, Git или сообщения.

## Сессии и защита

- Пароли: Argon2id, 64 MiB, time cost 3, parallelism 1; длина при создании 12–128 символов. Логины ASCII нормализуются в нижний регистр; пароль не нормализуется.
- Сессия: случайный 256-bit opaque token; в PostgreSQL хранится только SHA-256. По умолчанию срок 60 минут, без sliding expiration/refresh. Выход отзывает текущую сессию; повторное предъявление старой cookie запрещено. BLOCKED/DISABLED и изменения ролей проверяются по БД на каждом запросе.
- Браузер: `__Host-fk_session`, Secure, HttpOnly, SameSite=Strict, Path=/, без Domain. Браузер использует HTTPS. Идентификатор сессии передаётся только через Set-Cookie и не возвращается в JSON; JS не получает его и не сохраняет в localStorage/sessionStorage. Единственный клиент MVP — браузер; отдельного bearer-входа нет, Authorization на защищённых маршрутах отклоняется с 401.
- CSRF: login и изменяющие запросы с session cookie требуют Origin из FK_ALLOWED_ORIGINS; отсутствующий, null и сторонний Origin запрещены с 403. Авторизация в заголовке не позволяет обойти cookie/Origin-проверку. CORS для сторонних сайтов не включён.
- Redis ограничивает login по аккаунту и peer IP: 10/60 попыток за 60 секунд по умолчанию. Недоступность Redis запрещает вход (503). За HTTPS proxy peer IP соответствует proxy, пока отдельно не настроен trusted forwarding; X-Forwarded-For не принимается от произвольного клиента.
- Auth/user ответы имеют Cache-Control: no-store; validation errors не отражают введённые пароли/токены. Gateway задаёт CSP и запрет встраивания в frame.
- Создание пользователя требует user.manage + role.assign и сессию не старше 5 минут. После этого срока нужно выйти и войти снова.
- Auth и создание/назначение ролей записываются в AuditEvent без credentials. UPDATE/DELETE AuditEvent отклоняется PostgreSQL trigger. Actor UUID сохраняется как историческая ссылка без cascade удаления истории.

В Compose параметры задаются через `.env`: `FK_ALLOWED_ORIGINS` (JSON-массив, default `["https://localhost:8443"]`), `FK_SESSION_MINUTES`, `FK_LOGIN_WINDOW_SECONDS`, `FK_LOGIN_ACCOUNT_LIMIT`, `FK_LOGIN_IP_LIMIT`. Permission не заменяет будущую проверку области доступа к бизнес-объектам; в этом этапе бизнес-объектов ещё нет.

## API

- POST /api/v1/auth/login → только `{ "user": ... }`; устанавливает HttpOnly cookie при разрешённом Origin.
- GET /api/v1/auth/me → user с актуальными roles и permissions.
- POST /api/v1/auth/logout → 204; отзывает текущую сессию.
- GET /api/v1/dashboard → готовность компонентов, требует dashboard.view.
- GET /api/v1/users → первые 100 пользователей, требует user.view.
- POST /api/v1/users → создание и назначение ролей, требует user.manage + role.assign и свежий вход.
- GET /api/v1/version теперь требует update.view согласно матрице. Диагностический /api/v1/health остаётся публичным и не содержит credentials.

401: отсутствующая/недействительная сессия. 403: отсутствующий permission, запрещённый Origin или необходимость повторного входа. 429: ограничение login. Ошибки соответствуют API Contract. Session table и password_hash — технические расширения User, не новые бизнес-состояния.

## Проверки и границы

Сценарий независимой приёмки с шагами, ожидаемыми результатами и шаблоном отчёта: [Authentication + RBAC review v0.1](../testing/auth-rbac-review-v0.1.md). Наличие сценария не означает, что ревью выполнено.

Запуск: scripts/check.sh, check-sast.sh, check-secrets.sh, check-dependencies.sh, test-security-gates.sh, затем check-integration.sh с работающим Compose.

RBAC-тесты используют отдельную временную PostgreSQL schema и реальные авторизованные requests к маршрутам, подключённым только тестами. Для каждого permission проверяются все роли, включая deny для пользователя без ролей. Бизнес-сценарии и object scope добавляются вместе с соответствующими модулями.

Browser tests создают случайные временные аккаунты через helper из backend/tests (не входит в runtime image). Credentials хранятся только в игнорируемом deploy/local/e2e.json с mode 0600. После тестов удаляются только пользователи с уникальным префиксом этого запуска и их сессии; аудит сохраняется. Не запускайте проверки против production. После аварийного прерывания очистите собственную fixture командой `FK_TEST_INTEGRATION=1 uv run --frozen python -m tests.e2e_accounts cleanup` из backend с экспортированным .env, затем повторите тест.

MFA/SSO, восстановление паролей, изменение пользователей/ролей через UI, production installer и продуктовый E2E импорта не входят в этап. Перед серьёзным пилотом обязательны независимое security review/pentest и усиленная административная аутентификация из Security v0.1; recent authentication не объявляется заменой MFA.
