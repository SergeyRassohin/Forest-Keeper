# Независимая приёмка Authentication + RBAC — 19.10.2026

Связанные [issue #5](https://github.com/SergeyRassohin/Forest-Keeper/issues/5) и [PR #3](https://github.com/SergeyRassohin/Forest-Keeper/pull/3). **Первичный результат: 34 PASS, 1 FAIL; этап пока не принят.** Обязательный WEB-02 требует исправления и независимой повторной проверки. BLOCKED/NOT RUN нет.

## Версия и независимость

- Проверен чистый `main`: `41faa11a8b7ee9d5959ca6a3fd29d9079bb7fb74`.
- Base PR: `2772fc6ee9e303bd4dad5b5fd3f17c8d5770eb9b`; merged feature HEAD: `ea19abe2a77f8329e5a37076764f776ec7556d76`.
- Проверяющий: отдельный агент Codex `/root/independent_review`, не писавший проверяемую реализацию. В этом прогоне самостоятельно прочитал issue, актуальный сценарий, authentication/security/API/testing/local-development docs и XLSX, проверил runtime diff, миграцию, gateway, frontend и тесты; самостоятельно запустил все gates и дополнительные probes.
- Дата выполнения: 2026-10-19 UTC. Часы в сырых gate logs — UTC; даты пользователя — Europe/Moscow.
- Основание: AGENTS.md «Security-critical changes require independent verification». Этот отчёт не продолжает и не переиспользует старый bearer-прогон 15 октября.

## Среда и изоляция

Cloud Linux; Python3.13.16, uv0.12.23, Node24.19.0/npm11.9.0, Docker28.4.0/Compose2.40.3, Chromium154.0.8037.57. PostgreSQL17+pgvector и Redis7.4 взяты из штатных образов. Полные версии, immutable image IDs и checksums находятся в [evidence.json](auth-rbac-acceptance-2026-10-19/evidence.json).

Frozen `uv sync --frozen`, `npm ci`, dev-init, proxy-aware BuildKit build и Compose startup выполнены заново. Контрольная версия схемы `0002_auth`; публичный health200 с api/database/redis=ok. Runtime backend app tree SHA-256 `f08fe135281083b087c394225d9c6434967acee0a779ecca3b28ddd266c6c40e` совпал с checkout; nginx config и все3 frontend/dist файла побайтно совпали с контейнерами.

Штатные integration/browser gates используют свои временные схемы, Redis keys и e2e-пользователей в локальной development-среде. Дополнительный полный acceptance выполнен на отдельном Compose project `fk-acceptance-20261019`: собственные PG/Redis/backend/frontend, отдельный PostgreSQL volume, loopback ports15432/16379/18000/18443. Общие сервисы не останавливались. Origin `https://localhost:18443`; базовые account/IP limits10000 нужны для полного прогона, отдельные limit-сценарии используют2/73 и IP2. Созданы уникальные синтетические ADMIN, VIEWER, REVIEWER, DATA_OWNER, ADMIN+REVIEWER и пользователь без ролей с разными случайными паролями.

HTTPS API проверяет сертификат с локальным CA. Дополнительный Chromium использует pin точного SPKI локального сертификата; глобальное отключение проверки TLS не применялось. Штатный browser gate использует документированную настройку Playwright для локального самоподписанного сертификата. Внешний TLS и проверки сертификатов при установке/сборке не отключались.

## Обязательные gates и CI

| Проверка | Результат | Evidence |
| --- | --- | --- |
| scripts/check.sh | exit0; backend8passed, frontend9passed; lint/format/mypy/build/TS checks PASS | [log](auth-rbac-acceptance-2026-10-19/check.log) |
| scripts/check-sast.sh | exit0; Bandit656LOC,0findings/0skips; ESLint security0findings | [log](auth-rbac-acceptance-2026-10-19/check-sast.log) |
| scripts/check-secrets.sh | exit0;78commits+tracked snapshot,0leaks | [log](auth-rbac-acceptance-2026-10-19/check-secrets.log) |
| scripts/test-security-gates.sh | exit0;3negativefixtures отвергнуты B602/security-eval/github-pat | [log](auth-rbac-acceptance-2026-10-19/test-security-gates.log) |
| scripts/check-dependencies.sh | exit0; pip-audit/npm audit0vulnerabilities | [log](auth-rbac-acceptance-2026-10-19/check-dependencies.log) |
| scripts/check-integration.sh | exit0; backend222passed+browser5passed | [log](auth-rbac-acceptance-2026-10-19/check-integration.log) |

Всего штатных тестов **244 passed, 0 failed, 0 skipped**: backend230, frontend9, Chromium5. Deselected222 при unit и8 при integration — разделение одной коллекции, не skipped; все230 backend cases выполнены. В каждом pytest-проходе есть один Starlette/httpx deprecation warning; это не пропущенный тест и не suppressed finding. Собственный acceptance дополнительно выполнил195 комбинаций39permissions×5ролей и25 прямых operation×role requests, реальные browser/DB/failure probes. Их не прибавляем к244 как будто это штатные testcases.

Самостоятельно подтверждён GitHub Actions **SUCCESS** для того же полного SHA: [run39250342464](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39250342464), push/main, validate job success. CI не заменяет независимый сценарий.

## Результаты каждого ID

| ID | Статус | Фактическое доказательство |
| --- | --- | --- |
| AUTH-01 | PASS | HTTPS login/me and case-folded login HTTP200, identical user; login JSON only user, cookie omitted, sessions distinct. |
| AUTH-02 | PASS | Wrong/unknown login identical INVALID_CREDENTIALS401, no Set-Cookie and no session insertion. |
| AUTH-03 | PASS | BLOCKED and DISABLED both deny valid password with same generic401; own fixture restored ACTIVE. |
| AUTH-04 | PASS | Malformed JSON, extra field, empty values and password129 all422, no echoed input/traceback, session count unchanged. |
| AUTH-05 | PASS | Four protected GETs and valid anonymous POST users401; public health200, no credentials. |
| AUTH-06 | PASS | Success/error auth/user no-store, no password_hash, no WWW-Authenticate Bearer; OpenAPI LoginResponse only user. |
| SESSION-01 | PASS | Actual Chromium cookie Secure/HttpOnly/Strict/Path=/ host localhost; document.cookie cannot read it; localStorage/sessionStorage empty; login JSON only user. API probe additionally checks no Domain attribute. |
| SESSION-02 | PASS | Browser reload preserves login; UI logout204 removes cookie, reload shows login; replay of captured old cookie401. |
| SESSION-03 | PASS | Random/modified/257-char cookies401; valid session in Bearer, Basic and empty Authorization401 with and without cookie. |
| SESSION-04 | PASS | Actual DB expires owned session; API401 and dashboard retry returns UI to login. Separately aborted /auth/me displays connection error, not anonymous login. |
| SESSION-05 | PASS | Existing sessions immediately rejected after BLOCKED and DISABLED, fixture restored. |
| CSRF-01 | PASS | Admin cookie logout/users missing or foreign Origin403; session remains live; User count unchanged. |
| CSRF-02 | PASS | Login missing/null/foreign Origin403 without Set-Cookie or inserted session; exact allowed Origin200. |
| CSRF-03 | PASS | Authorization never authenticates; cookie mutations missing/null Origin403 without changes (SESSION-03/CSRF-01 real probes). |
| WEB-01 | PASS | Verified HTTPS gateway CSP self/frame-ancestors none and XFrameOptions DENY; evil-origin preflight405/anonymousGET401 no ACAO; Chromium cross-origin iframe blocked by policy. |
| WEB-02 | FAIL | Incorrect password401 clears field; real login fetch abort shows native English Failed to fetch instead of an understandable Russian transport-error message. Password cleared and login not granted. |
| RBAC-01 | PASS | All25 direct HTTPS operation/role combinations match table, including no-role; denied POSTs preserve User count. |
| RBAC-02 | PASS | Independent ZIP/XML XLSX reader, catalogue SHA and all39 entries agree; 195 cookie-authenticated test-only dependency requests agree, unknown permission403. |
| RBAC-03 | PASS | Real ADMIN and ADMIN+REVIEWER me permissions exactly match XLSX union; ADMIN lacks business permissions and rule.activate. |
| RBAC-04 | PASS | Deleting own DATA_OWNER role changes live me to no permissions and dashboard403; fixture restored. |
| USER-01 | PASS | ADMIN201 creates REVIEWER; new account logs in with correct hash and cannot administer. |
| USER-02 | PASS | Repeated role deduplicated; exact and uppercase duplicate logins409, no duplicate account. |
| USER-03 | PASS | SUPER_ADMIN/status/password_hash/extra fields, passwords11/129 all422, no partial account or echoed secret. |
| USER-04 | PASS | Admin session aged6min gives REAUTH_REQUIRED403 without insertion; real new login restores201. |
| USER-05 | PASS | ADMIN panel creates REVIEWER through UI201 and clears password; VIEWER and new REVIEWER have no panel; direct reviewer users request403. |
| BOOT-01 | PASS | Real bootstrap subprocess on empty disposable DB: one ADMIN, Argon2id, actor NULL and target User UUID. |
| BOOT-02 | PASS | Repeat refused unchanged; two concurrent subprocesses on empty isolated schema returned [0,1], exactly one account; schema removed. |
| STORE-01 | PASS | All stored password hashes Argon2id64MiB/t3/p1; each captured session found by SHA256 only; independent logins distinct. |
| AUDIT-01 | PASS | All5 required events observed; login/logout actor=target; denied actorNULL known/unknown targets; create/roles actorADMIN and assigned roles payload correct. |
| AUDIT-02 | PASS | 42 unique synthetic credential/session/DB-secret values compared in-process against62 AuditEvents and114813bytes runtime logs backend/frontend/PostgreSQL/Redis:0 matches. Role payload contains only assigned roles. |
| AUDIT-03 | PASS | Actual runtime DB-role UPDATE and DELETE rejected by append-only trigger in separate transactions; rollback preserves event. |
| FAIL-01 | PASS | Exact account limit2/window73:401,401,429 Retry-After73; after actual74s next request401, no manual key expiry. |
| FAIL-02 | PASS | Three distinct logins and three forged XFF addresses share peer limit2:401,401,429; gateway default clients share proxy peerIP as documented. |
| FAIL-03 | PASS | Stopped dedicated Redis container: loginAUTH_UNAVAILABLE503, no cookie/session insertion; restarted service, health200 and login200. |
| FAIL-04 | PASS | Stopped dedicated PostgreSQL: health503 and protected me500 generic without credentials/traceback; restarted DB, health200 and same session me200. |

Workbook SHA-256 `1d3fcff5fda90e830845f87c9032bcc91b7877ef53f4c79cd06e9a1c2176470e`. Независимый ZIP/XML reader прочитал роли из XLSX header; runtime catalogue не использовался как источник ожидаемых результатов. Test-only routes существовали лишь в локальном TestClient app и не добавлялись в продукт. Они подтверждают policy/dependency для будущих permissions, не будущие business endpoints/object scope.

FAIL-02 также перепроверен реальным HTTPS nginx→uvicorn путём: backend временно настроен на IP limit2/account1000 с новым Redis prefix;3разных логина и3поддельных X-Forwarded-For дали401/401/429. Конфигурация возвращена. FAIL-01 выждал реальные74сек после окна73, без EXPIRE/удаления ключей. FAIL-03/04 останавливали настоящие отдельные контейнеры, не mocks/только refusedport. Восстановление PostgreSQL подтвердило работоспособность той же существовавшей сессии.

## Найденный дефект WEB-02

**Severity: low, UX; блокирует формальную приёмку этого сценария до исправления.** Секреты не раскрываются, несанкционированного входа нет.

В [frontend/src/api.ts](../../../frontend/src/api.ts#L52) rejected fetch не преобразуется в понятную ошибку, а [App.tsx](../../../frontend/src/App.tsx#L161) показывает native Error.message. В русскоязычном UI получается `Failed to fetch`.

Воспроизведение на проверенном SHA:

1. Открыть форму входа в Chromium с чистым context.
2. Перехватить **только** `**/api/v1/auth/login` через Playwright `page.route(..., route => route.abort("failed"))`; API /auth/me оставить рабочим.
3. Ввести синтетические валидные credentials и нажать «Войти».
4. Фактически alert содержит `Failed to fetch`; пароль очищен, форма входа остаётся, доступа нет.
5. Ожидается понятное русскоязычное сообщение о временной сетевой недоступности/возможности повторить вход, с сохранением очистки пароля и отсутствия авторизации.

Повторная проверка после исправления пока **NOT RUN**, новый runtime SHA пока не предоставлен. Статус относится только к pending retest дефекта; все35 обязательных ID уже исполнены, среди них WEB-02=FAIL. Не считать исправление завершённым лишь по новому unit-тесту. Требуются независимый browser retest WEB-02, затронутые auth/UI проверки и обязательные gates/CI на новом SHA.

## Безопасность evidence и очистка

Ни raw password, ни session cookie/token, ни DB password, ни HAR, ни приватный Compose config в Git не добавлены. Сверка62AuditEvents и114813bytes логов backend/frontend/PostgreSQL/Redis по42уникальным синтетическим секретам дала0совпадений; проверяющий сравнивал значения внутри процесса, без вывода. Аудит role assignments содержит только роли; audit snapshot SHA-256 `00e0587ebb5f1d231d6019409ee639711b2a44b3c0205f5563ad98321fcf9a95`.

Удалены11собственных accounts и их sessions; чужие accounts не затронуты, AuditEvent62строки сохранены без изменения. Bootstrap race schema удалена. Собственные rate keys находились только в disposableRedis. Штатный e2e helper очистил свои fixtures. Disposable project останавливается без удаления audit volume; private credential files удаляются после завершения итоговых проверок/отчёта.

Ошибки первоначальной подготовки harness не объявлены дефектами продукта: OpenAPI запрошен на gateway вместо внутреннего backend; Docker tmpfs очищался при stop/start PostgreSQL; Playwright response.headers() скрывал Set-Cookie вместо allHeaders(). После исправления harness прогоны соответствующих сценариев выполнены заново; итоговые PASS относятся к повторённым реальным проверкам. WEB-02, напротив, воспроизведён как дефект продукта и оставлен FAIL.

## Вывод

На `41faa11a8b7ee9d5959ca6a3fd29d9079bb7fb74` основная защита Authentication/RBAC подтверждена, все gates и CI зелёные. **Формально Этап1 пока не принимается: исправить WEB-02 и независимо повторить проверку на новом SHA.** Остальные34обязательных ID имеют PASS; BLOCKED/NOT RUN среди обязательных ID нет.

Границы неизменны: нет MFA/SSO/password recovery, редактирования пользователей/ролей в UI, business object scope и будущих business endpoints. Recent authentication не заменяет MFA. Промышленный пилот требует отдельного pentest/усиленной административной аутентификации; Этап2 в этой задаче не начат.
