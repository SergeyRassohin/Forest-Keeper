# Cookie-сессии веб-приложения — 19 октября 2026

Ревизия PR #3 относительно `ac1e7dc619c3f4fa233622456a5c6bda6493293d`: удалены bearer-вход, access_token/token_type из JSON и Bearer challenge. Единственный клиент MVP — браузер. Сессия передаётся только в Secure/HttpOnly/SameSite=Strict cookie; login и изменяющие запросы с cookie требуют разрешённый Origin. Решение зафиксировано в decision log, API contract и authentication.md.

Проверено в облачной development-среде с PostgreSQL 17/pgvector, Redis 7.4 и Chromium 154. Контейнеры пересобраны из текущих исходников; миграция осталась `0002_auth`. Этот отчёт относится к ревизии, содержащей данный файл; CI проверяется для SHA итогового commit. [Старый отчёт](auth-rbac-2026-10-15.md) и его probes сохранены как исторические, новый контракт ими не проверялся.

## Автоматические проверки

| Проверка | Результат |
| --- | --- |
| `scripts/check.sh` | Ruff, format, mypy, ESLint, TypeScript/build/E2E typecheck — PASS; backend 8 passed, frontend 9 passed |
| `scripts/check-sast.sh` | Bandit и frontend security ESLint — PASS, находок нет |
| `scripts/check-dependencies.sh` | pip-audit и npm audit — PASS, известных уязвимостей нет |
| `scripts/check-secrets.sh` | Git history и все tracked contents, включая новые отчёты/артефакты — PASS, no leaks |
| `scripts/test-security-gates.sh` | Все 3 отрицательные fixtures отклонены ожидаемыми правилами |
| `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium scripts/check-integration.sh` | 222 backend integration/API + 5 browser — PASS; schema head `0002_auth`; fixture cleanup выполнен |

Итого **244 passed** в штатном полном прогоне: 230 backend, 9 frontend, 5 browser. Deselected разделяют unit/integration; skipped нет. Первый typecheck нового E2E выявил неоднозначный тип массива headers; тип исправлен, полный check.sh повторно прошёл. Предупреждение Starlette о будущем изменении TestClient остаётся неблокирующим.

## Ключевые регрессии

- Реальный браузер входит, обновляет страницу, получает dashboard и создаёт пользователя с ADMIN. JSON каждого browser login содержит только `user`.
- OpenAPI работающего backend также содержит только `user` в LoginResponse; access_token/token_type удалены из схемы.
- Отсутствующий, `null` и сторонний Origin на login дают 403 без Set-Cookie и новой DB session. Разрешённый Origin допускает вход.
- POST создания пользователя без разрешённого Origin не создаёт пользователя. Полные 195 permission/role проверок теперь используют cookie и Origin.
- Даже действующее значение сессии в Authorization без cookie не авторизует пользователя. Authorization также отвергается при наличии cookie, включая пустой заголовок; logout не выполняется. После этих отказов обычная cookie-сессия остаётся действующей.
- Logout удаляет cookie и отзывает серверную запись; повторная установка старой cookie даёт 401 в API и browser tests.
- В БД остаётся SHA-256 идентификатора сессии, пароли Argon2id; token отсутствует в JSON. Роли, статус, expiry и audit проверяются прежними тестами.

## Независимая проверка

Отдельный агент, не писавший реализацию, прочитал текущий runtime/test diff и запустил регрессии в собственной временной PostgreSQL schema: **9 passed, 210 deselected**, 3.14 секунды. Блокирующих findings нет. Независимый агент не менял source и не публиковал сообщения GitHub.

Проверен незакоммиченный diff относительно `ac1e7dc`; SHA-256 проверенного runtime/test diff: `10a2fef8eb047387316b182bececfd21ad6fa9e87edf5bde8e930939707c0f49`, timestamp `2026-10-19T09:02:55Z`. Полный CI/browser-прогон не повторялся независимым агентом; его выполнил основной агент. Это целевая повторная проверка изменения, не промышленный pentest.

Известная граница: публичный login не использует Authorization даже если клиент прислал этот заголовок; для входа всё равно нужны пароль и разрешённый Origin. Отказ любого Authorization обещан на защищённых маршрутах. MFA, recovery и будущие бизнес/object-scope проверки не входят в эту ревизию. Merge не выполняется этим изменением.
