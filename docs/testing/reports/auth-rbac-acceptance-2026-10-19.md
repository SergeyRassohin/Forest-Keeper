# Независимая приёмка Authentication + RBAC — 19.10.2026

Связанные [issue #5](https://github.com/SergeyRassohin/Forest-Keeper/issues/5) и [PR #3](https://github.com/SergeyRassohin/Forest-Keeper/pull/3). **Итог: 35 PASS, 0 FAIL, 0 BLOCKED, 0 NOT RUN.** Дефект WEB-02 найден в первичном прогоне и закрыт после исправления и независимой повторной проверки.

## Версии и независимость

- Полный исходный acceptance: чистый `main` **41faa11a8b7ee9d5959ca6a3fd29d9079bb7fb74**, результат 34 PASS / 1 FAIL.
- Исправление и итоговый runtime SHA: **40da5aca6bec33c11ec417c975fec26cdc05c9eb**, branch `fix/auth-acceptance-web02`.
- Base PR #3: `2772fc6ee9e303bd4dad5b5fd3f17c8d5770eb9b`; merged feature HEAD: `ea19abe2a77f8329e5a37076764f776ec7556d76`.
- Проверяющий: отдельный агент Codex `/root/independent_review`, не писавший ни исходную реализацию, ни runtime-исправление WEB-02. Самостоятельно прочитал issue, актуальный сценарий, authentication/security/API/testing/local-development docs и XLSX; проверил код, миграцию, gateway, frontend, тесты; лично запустил gates и acceptance probes обоих прогонов.
- Дата: 2026-10-19 UTC; логи используют UTC, пользовательский timezone — Europe/Moscow.
- Основание: AGENTS.md «Security-critical changes require independent verification». Старые отчёты 15 октября о bearer-flow не использованы как доказательство актуального контракта.

## Среда и изоляция

Cloud Linux; Python 3.13.16, uv 0.12.23, Node 24.19.0 / npm 11.9.0, Docker 28.4.0 / Compose 2.40.3, Chromium 154.0.8037.57; PostgreSQL 17 + pgvector и Redis 7.4. Версии, image IDs и checksums: [исходные evidence](auth-rbac-acceptance-2026-10-19/evidence.json), [retest evidence](auth-rbac-acceptance-2026-10-19/retest-40da5ac/evidence.json).

Заново выполнены frozen `uv sync --frozen`, `npm ci`, dev-init, proxy-aware BuildKit build и Compose startup. Schema revision `0002_auth`; health 200 с api/database/redis=ok. Backend app tree SHA-256 `f08fe135281083b087c394225d9c6434967acee0a779ecca3b28ddd266c6c40e` совпал с checkout; nginx и все три frontend/dist файла побайтно совпали с исходным контейнером. После исправления все три новых frontend/dist файла также побайтно сверены с пересобранным контейнером.

Полный дополнительный acceptance выполнен на отдельном project `fk-acceptance-20261019`: собственные PG/Redis/backend/frontend, отдельный PostgreSQL volume, loopback ports 15432/16379/18000/18443. Общие сервисы не останавливались. Origin `https://localhost:18443`; для основного прогона account/IP limits=10000, для специальных случаев account=2/window=73 и IP=2. Созданы собственные синтетические ADMIN, VIEWER, REVIEWER, DATA_OWNER, ADMIN+REVIEWER и no-role с разными случайными паролями.

Штатные integration gates используют собственные временные schemas/Redis keys/e2e accounts в local development-среде. Дополнительный retest использовал отдельного уникального synthetic VIEWER на текущем HTTPS UI `https://localhost:8443`; изменялась только его собственная session expiry. Все fixtures затем очищены, аудит сохранён.

HTTPS API проверяет сертификат локальным CA. Дополнительный Chromium использует pin точного SPKI локального сертификата без глобального отключения TLS validation. Штатный browser gate использует документированную настройку Playwright для локального самоподписанного сертификата. TLS при установке/сборке не отключался.

## Gates и CI

Все шесть gates **лично выполнены заново на обоих SHA**. Команды: `bash scripts/check.sh`, `bash scripts/check-sast.sh`, `bash scripts/check-secrets.sh`, `bash scripts/test-security-gates.sh`, `bash scripts/check-dependencies.sh`, `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium bash scripts/check-integration.sh`.

| Gate | 41faa11, исходный полный прогон | 40da5ac, независимый retest |
| --- | --- | --- |
| check | exit 0; backend 8 + frontend 9; lint/format/mypy/build/TS PASS | [exit 0, те же 17 tests](auth-rbac-acceptance-2026-10-19/retest-40da5ac/check.log) |
| check-sast | exit 0; Bandit 656 LOC, 0 findings/skips; ESLint security 0 findings | [exit 0, 0 findings](auth-rbac-acceptance-2026-10-19/retest-40da5ac/check-sast.log) |
| check-secrets | exit 0; 78 commits + tracked snapshot, 0 leaks | [exit 0; 79 commits + tracked snapshot, 0 leaks](auth-rbac-acceptance-2026-10-19/retest-40da5ac/check-secrets.log) |
| test-security-gates | exit 0; три negative fixtures отвергнуты | [exit 0; B602 / security-eval / github-pat](auth-rbac-acceptance-2026-10-19/retest-40da5ac/test-security-gates.log) |
| check-dependencies | exit 0; pip-audit / npm audit: 0 vulnerabilities | [exit 0; 0 vulnerabilities](auth-rbac-acceptance-2026-10-19/retest-40da5ac/check-dependencies.log) |
| check-integration | exit 0; backend 222 + browser 5 passed | [exit 0; backend 222 + browser 6 passed](auth-rbac-acceptance-2026-10-19/retest-40da5ac/check-integration.log) |

Исходный прогон: **244 passed, 0 failed, 0 skipped**. Итоговый retest: **245 passed, 0 failed, 0 skipped** — backend 230, frontend 9, Chromium 6. Deselected 222 при unit и 8 при integration разделяют одну коллекцию: все 230 backend cases выполнены. В каждом pytest-проходе есть один Starlette/httpx deprecation warning; тесты и findings не подавлялись. Дополнительные 195 независимых permission×role и 25 operation×role запросов, browser/DB/failure probes не прибавляются к штатному числу tests.

Самостоятельно подтверждён GitHub Actions SUCCESS на exact SHA:

- Исходный `41faa11`: [run 39250342464](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39250342464), push/main, validate SUCCESS.
- Итоговый `40da5aca6bec33c11ec417c975fec26cdc05c9eb`: [run 39253637438](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39253637438), push, validate SUCCESS.

CI не заменяет независимый сценарий. Исходные логи сохранены рядом с [историческим evidence.json](auth-rbac-acceptance-2026-10-19/evidence.json); новые логи и результаты находятся в `retest-40da5ac/`.

## Результаты каждого обязательного ID

Таблица показывает итоговый статус. Все 35 ID лично исполнены при первоначальном полном прогоне; после исправления повторены WEB-02 и затронутые auth/UI scenarios, все gates и exact-SHA CI. Backend, migration, nginx, role matrix и их runtime-код между SHA не менялись, поэтому исходные реальные bootstrap/failure/storage доказательства сохраняют силу; полный разрушительный прогон всех 35 ID заново не выдаётся за выполненный.

| ID | Итог | Фактическое доказательство |
| --- | --- | --- |
| AUTH-01 | PASS | HTTPS login/me и логин в другом регистре: 200, тот же User; JSON только user, cookie отсутствует в JSON, новые сессии различаются. |
| AUTH-02 | PASS | Неверный пароль и неизвестный login: одинаковый INVALID_CREDENTIALS 401; нет Set-Cookie и новых AuthSession. |
| AUTH-03 | PASS | BLOCKED и DISABLED запрещают верный пароль с тем же общим 401; собственный аккаунт восстановлен. |
| AUTH-04 | PASS | Malformed JSON, extra fields, пустые поля и пароль длиной 129: 422 без отражения секретов/traceback; сессии не созданы. |
| AUTH-05 | PASS | Четыре защищённых GET и валидный анонимный POST users: 401; публичный health: 200 без credentials. |
| AUTH-06 | PASS | Auth/user success/error: no-store, нет password_hash и Bearer challenge; OpenAPI LoginResponse содержит только user. Дополнительно проверены users 200/201/409/422. |
| SESSION-01 | PASS | Chromium: Secure, HttpOnly, Strict, Path=/, без Domain; document.cookie не видит сессию, local/session storage пусты. Повторено на 40da5ac. |
| SESSION-02 | PASS | Reload сохраняет вход; UI logout 204 удаляет cookie; reload показывает вход, replay старой cookie: 401. Повторено на 40da5ac. |
| SESSION-03 | PASS | Случайная/изменённая/257-символьная cookie: 401. Bearer с действующей сессией, Basic и пустой Authorization: 401 с cookie и без неё; header-flow повторно отвергнут на 40da5ac. |
| SESSION-04 | PASS | Реальное истечение expires_at собственной сессии: API 401, UI снова предлагает вход; отдельный отказ auth/me показывает сетевую ошибку. DB-expiry UI повторён на 40da5ac. |
| SESSION-05 | PASS | Изменение собственного аккаунта на BLOCKED/DISABLED немедленно запрещает существующую сессию. |
| CSRF-01 | PASS | ADMIN cookie: logout/users без Origin и со сторонним Origin — ORIGIN_NOT_ALLOWED 403; сессия жива, User count прежний. Logout повторён на 40da5ac. |
| CSRF-02 | PASS | Login без Origin, с null/foreign: 403 без cookie/новой сессии; allowed Origin: 200. Повторено на 40da5ac. |
| CSRF-03 | PASS | Authorization не авторизует; cookie mutation без allowed Origin и с null: 403 без изменений. Повторено на 40da5ac. |
| WEB-01 | PASS | Реальные CSP self/frame-ancestors none и X-Frame-Options DENY; foreign CORS отсутствует; Chromium блокирует iframe другого origin. |
| WEB-02 | PASS | На 41faa11 был FAIL: Failed to fetch. На 40da5ac независимый Chromium abort login показывает «Не удалось подключиться к серверу. Повторите попытку.»; пароль пуст, сессии нет. Wrong-password и HTTP 503 также перепроверены. |
| RBAC-01 | PASS | Все 25 прямых HTTPS operation×role запросов совпадают с таблицей, включая no-role; запрещённые POST не создают User. |
| RBAC-02 | PASS | Независимый ZIP/XML reader XLSX: SHA и все 39 permissions совпали; 195 authenticated dependency requests соответствуют XLSX, неизвестный permission: 403. |
| RBAC-03 | PASS | Реальные ADMIN и ADMIN+REVIEWER имеют точное объединение XLSX-прав; ADMIN один не получает business permissions и rule.activate. |
| RBAC-04 | PASS | Удаление собственной DATA_OWNER role сразу убирает permissions и даёт dashboard 403; роль восстановлена. |
| USER-01 | PASS | ADMIN создаёт REVIEWER: 201; новый пользователь входит с правильным хешем пароля, users ему запрещён. |
| USER-02 | PASS | Повторные роли дедуплицированы; дубликаты login, включая uppercase: 409 без второго аккаунта. |
| USER-03 | PASS | SUPER_ADMIN/status/password_hash/extra и пароли длиной 11/129: 422 без частично созданного User и отражения секретов. |
| USER-04 | PASS | ADMIN session старше 6 минут: REAUTH_REQUIRED 403 без вставки; новый login восстанавливает создание: 201. |
| USER-05 | PASS | UI ADMIN создаёт REVIEWER: 201, password field очищается; у VIEWER/REVIEWER нет панели, прямой users: 403. Штатный browser case повторён на 40da5ac. |
| BOOT-01 | PASS | Настоящий bootstrap subprocess на пустой disposable DB: один ADMIN, Argon2id, ADMIN_BOOTSTRAPPED actor NULL, target User UUID. |
| BOOT-02 | PASS | Повторный bootstrap отказал, password hash прежний; два одновременных subprocess на пустой отдельной schema: exit codes [0,1], ровно один User; schema удалена. |
| STORE-01 | PASS | Все пароли Argon2id с m=65536,t=3,p=1; сохранённые сессии находятся только по SHA-256, не по raw cookie; разные входы дают разные значения. |
| AUDIT-01 | PASS | Все пять требуемых event types наблюдались; login/logout actor=target, denied actor NULL с известным/неизвестным target; create/roles actor ADMIN, payload содержит роли. |
| AUDIT-02 | PASS | 42 уникальных синтетических секрета сопоставлены внутри процесса с 62 AuditEvents и 114813 bytes логов backend/frontend/PG/Redis: 0 совпадений. |
| AUDIT-03 | PASS | UPDATE и DELETE под runtime DB role отклонены append-only trigger в отдельных транзакциях; rollback сохранил event без изменений. |
| FAIL-01 | PASS | Точный account limit=2/window=73: 401,401,429 и Retry-After=73; после реальных 74 секунд снова 401, без ручного истечения Redis keys. |
| FAIL-02 | PASS | Три разных логина и три forged XFF при IP limit=2: 401,401,429; подтверждено TestClient и настоящим HTTPS nginx→uvicorn путём. |
| FAIL-03 | PASS | Остановлен отдельный Redis container: login AUTH_UNAVAILABLE 503, без cookie/новой сессии; после запуска health/login 200. |
| FAIL-04 | PASS | Остановлен отдельный PostgreSQL container: health 503, protected me 500 с общим ответом без credentials/traceback; после запуска health 200 и прежняя сессия me 200. |

Workbook SHA-256 `1d3fcff5fda90e830845f87c9032bcc91b7877ef53f4c79cd06e9a1c2176470e`. Независимый ZIP/XML reader читал роли из header XLSX, не из runtime-каталога. Test-only routes подключались лишь к локальному TestClient app, не к продукту; они подтверждают policy/dependency будущих permissions, не будущие business endpoints/object scope.

FAIL-02 перепроверен реальным HTTPS nginx→uvicorn: IP=2/account=1000, новый Redis prefix; три разных login и три forged X-Forwarded-For дали 401/401/429. Конфигурация возвращена. FAIL-01 ждал реальные 74 секунды после окна 73 без ручного изменения TTL. FAIL-03/04 останавливали настоящие отдельные контейнеры; восстановление PostgreSQL подтвердило ту же сессию. Backend-код этих проверок не менялся в WEB-02 fix.

## Дефект WEB-02 и закрытие

**История: FAIL на 41faa11 → исправление 40da5ac → независимый PASS. Severity low (UX), приёмка блокировалась до исправления.** Секреты не раскрывались, несанкционированного входа не было.

В исходном коде rejected fetch в `frontend/src/api.ts:52` не преобразовывался в понятную ошибку; `App.tsx:161` показывал native Error.message. В русскоязычном UI появлялся `Failed to fetch`.

Воспроизведение: открыть форму в чистом Chromium context; перехватить только `**/api/v1/auth/login` через `page.route(..., route => route.abort("failed"))`, не ломая auth/me; ввести synthetic credentials и нажать «Войти». На исходном SHA alert был `Failed to fetch`, пароль очищался, форма оставалась, доступа не было.

В `40da5ac` fetch rejection преобразуется в «Не удалось подключиться к серверу. Повторите попытку.». Отдельный проверяющий прочитал diff и повторил этот сценарий на пересобранном реальном UI: точный русский alert, пустой пароль, нет session cookie, форма входа остаётся. Новый штатный browser regression также независимо выполнен. Все три frontend/dist файла сверены с контейнером.

Дополнительно независимо повторены реальные wrong-password 401, missing/null/foreign Origin для login и cookie logout, запрет Authorization, успешный cookie-only login и reload, DB expiry→UI login, logout/replay. Browser fulfillment HTTP 503 проверил сообщение «Вход временно недоступен. Повторите попытку.» и очистку пароля. Это retest UI-обработки outage; он не выдаётся за повторную остановку Redis/PG, которая выполнена в полном исходном прогоне на неизменившемся backend. [Sanitized retest transcript](auth-rbac-acceptance-2026-10-19/retest-40da5ac/independent-browser.log).

Новых findings нет. Обязательных BLOCKED/NOT RUN и незакрытых acceptance/security findings нет.

## Evidence и очистка

В Git не добавлены raw passwords, session cookies/tokens, DB passwords, HAR или private Compose config. Сверка 62 AuditEvents и 114813 bytes логов backend/frontend/PostgreSQL/Redis по 42 уникальным synthetic secrets дала 0 совпадений; сравнение выполнялось внутри процесса. Audit snapshot SHA-256 `00e0587ebb5f1d231d6019409ee639711b2a44b3c0205f5563ad98321fcf9a95`.

Первоначальные 11 собственных accounts и sessions удалены, 62 audit rows сохранены неизменными. Race schema удалена. Disposable project остановлен без удаления audit volume; private credentials/config удалены. При retest отдельный synthetic VIEWER и его sessions также удалены, его audit сохранён; private JSON удалён. Штатный e2e helper очистил свои fixtures. Чужие accounts и пользовательские volumes не затронуты.

Первоначальные ошибки harness исправлялись и не выдавались за product findings: OpenAPI запрашивался на gateway вместо internal backend; Docker tmpfs очищался при PostgreSQL stop/start; Playwright headers() скрывал Set-Cookie вместо allHeaders(). После исправления harness затронутые сценарии заново успешно выполнены. WEB-02 был отдельным воспроизведённым product defect; его FAIL и последующее закрытие сохранены в истории отчёта. Старые gate logs при обновлении получили только удаление лишних пустых строк в EOF.

## Вывод

**Независимая приёмка реализованного Этапа 1 на runtime SHA `40da5aca6bec33c11ec417c975fec26cdc05c9eb` завершена: 35 PASS, 0 FAIL/BLOCKED/NOT RUN; все gates и exact-SHA CI зелёные.** Отчёт и retest evidence готовы к сохранению в Git; первоначальная версия 41faa11 отдельно зафиксирована как 34 PASS / 1 FAIL и не объявляется принятой задним числом.

Границы: нет MFA/SSO/password recovery, редактирования ролей/статуса через UI, business object scope и будущих business endpoints. Recent authentication не заменяет MFA. Перед промышленным пилотом остаются отдельный pentest и усиленная административная аутентификация. Этап 2 в этой задаче не начат.
