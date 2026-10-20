# MVP: состояние реализации

## Итерация 1 — этап 0

Реализован запускаемый каркас по MVP Development Plan:

- backend: Python 3.13, FastAPI/Pydantic v2, SQLAlchemy, Alembic;
- PostgreSQL 17 с pgvector, Redis/RQ и отдельный worker;
- React/TypeScript/Vite Web Client с реальной проверкой готовности;
- HTTPS gateway для локальной разработки, случайные локальные credentials вне Git;
- frozen lockfiles, Docker Compose, скрипты запуска/проверки и GitHub Actions;
- миграция `0001_foundation`, которая включает pgvector.

Проверено в облачной Linux-среде:

- 6 backend unit-тестов, 4 frontend component-теста;
- 3 integration-теста: реальный PostgreSQL/vector SQL, задание в RQ worker и отсутствие health-таймаута на длительных операциях Alembic;
- 1 Playwright smoke-тест Web Client → HTTPS → API → PostgreSQL/Redis;
- lint, форматирование Python, mypy, TypeScript (включая E2E), production build;
- контейнерные сборки и запуск, перезапуск всех runtime-сервисов и повторная integration/E2E-проверка;
- Alembic downgrade → health 503 → upgrade → health 200, повторный upgrade;
- `pip-audit` и `npm audit`: известных уязвимостей не обнаружено после обновления Vitest до исправленной версии. Собственный editable backend проверяется тестами и статическими анализаторами, а не каталогом уязвимостей сторонних пакетов.
- отдельный SAST: Bandit для Python и ESLint security для TypeScript;
- Gitleaks: история Git и текущие tracked-файлы, с маскированием находок в выводе;
- отрицательные проверки security gates: синтетические shell injection, динамический eval и PAT отклоняются соответствующими scanner-правилами.

Команды: [локальная разработка](local-development.md). GitHub Actions для первоначального каркаса прошёл успешно, что подтверждено ревью. Результат CI для последующих ревизий проверяется отдельно.

В ревизии по замечаниям убран глобальный `statement_timeout=500` из engine: этот предел применяется только к health-транзакции через `SET LOCAL`. Alembic сохраняет обычную политику PostgreSQL; регрессионный тест выполняет операции дольше 500 мс до и после health, проверяя отсутствие утечки настройки в пул.

Этап 0 принят и объединён в main через [PR #2](https://github.com/SergeyRassohin/Forest-Keeper/pull/2). Проверки GitHub Actions прошли перед merge.

## Итерация 2 — этап 1

Реализованы [Authentication + RBAC](authentication.md): User/UserRole, Argon2id, отзываемые opaque-сессии, Secure/HttpOnly cookie, браузерный вход без выдачи идентификатора сессии в JSON, login/me/logout, фиксированные permissions по XLSX и создание пользователей через административный экран. Добавлены миграция 0002_auth, audit auth/role events, CSRF/Origin и Redis login limits. У ADMIN нет неявных бизнес-полномочий.

Локальная проверка после удаления bearer-входа 19.10.2026: 230 backend-тестов (8 unit, 222 integration/API, включая 195 комбинаций permission/role), 9 frontend-тестов и 5 HTTPS browser-тестов. Проверены bootstrap только в пустой БД, запрещённые запросы, блокировка/expiry/revocation, отсутствие credentials в JSON и ответах об ошибках, обязательный Origin, отказ Authorization и неизменяемость audit. Независимый агент повторно проверил diff и 9 целевых регрессий. [Отчёт](../testing/reports/auth-rbac-cookie-2026-10-19.md). SAST, SCA, Gitleaks и отрицательные security-fixtures входят в обязательные проверки. CI оценивается для актуального коммита ветки Authentication + RBAC.

Security-critical изменения требуют независимой проверки по AGENTS.md перед принятием. Этап 1 не включает MFA/SSO, recovery, изменение пользователей через UI и бизнес-object scopes. Новые auth-таблицы являются техническим расширением User и не вводят новые бизнес-статусы.

Canonical/matching/conflicts, Human Review, Decision Registry, AI/similarity, правила, полный бизнес-аудит, лицензирование и Update Service ещё не реализованы. Импорт добавлен в этапе 2 ниже. Модели не скачивались. Продуктовый E2E решений и capacity/performance acceptance всего MVP предстоят.

## Следующая итерация

Этап1 принят после полного независимого прогона [issue #5](https://github.com/SergeyRassohin/Forest-Keeper/issues/5), исправления WEB-02 и merge PR #6. Все35пунктов сценария PASS,245тестов и CI main прошли. Обновление CI Actions/runner принято через PR #4.

## Итерация 3 — этап 2

По [issue #7](https://github.com/SergeyRassohin/Forest-Keeper/issues/7) реализованы SourceSystem, ImportBatch, неизменяемый RawRecord, локальное persistent хранилище оригиналов, SHA-256 и фоновые jobs RQ. Добавлены защищённые source/import API, страницы ошибок/исходных записей, duplicate policy и явный retry новым пакетом, браузерный раздел «Импорт данных».

Форматы: UTF-8 CSV, первый worksheet XLSX, generic XML и документированный синтетический профиль 1С XML. Дополнительное ревью выявило четыре дефекта: CSV после потери границы записи, XLSX duration/специальные формулы, поздний enqueue и отмена медленных browser requests. Исправлены в `64afea2`, добавлены регрессии. Прогон исправлений до интеграции hardening: **393 backend (80 unit / 313 integration), 13 frontend и 7 browser — всего 413 PASS**, все security gates; независимый retest четырёх исправлений без открытых замечаний.

Capacity на исправленном runtime: два набора 100000×30 атрибутов, по 30000381 байт; обработаны за 20.818 и 20.174 сек, metadata p95=0.2263 сек при 10 сессиях. [PR #8](https://github.com/SergeyRassohin/Forest-Keeper/pull/8), [актуальный отчёт и exact-SHA CI](../testing/reports/stage2-import-review-fixes-2026-10-19.md), [Import subsystem](import.md). Первоначальные проверки `6380d5c` сохранены в [историческом отчёте](../testing/reports/stage2-import-acceptance-2026-10-19.md). Это исторический результат до синхронизации с production hardening; актуальный merge и итоговые проверки указаны ниже.

Этап 2 объединён в main через PR #8, merge commit `52de120`; [CI merge commit](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39415262127) прошёл. Вместе с hardening PR #10 проверены 408 backend (95 unit / 313 integration), 13 frontend и 7 browser — всего 428 PASS; production smoke включает общий том оригиналов. [Отчёт синхронизации](../testing/reports/stage2-main-sync-2026-10-20.md).

Этап 3 — нормализация и canonical model — реализован по [issue #12](https://github.com/SergeyRassohin/Forest-Keeper/issues/12) в [PR #13](https://github.com/SergeyRassohin/Forest-Keeper/pull/13): [описание](normalization.md), [acceptance report](../testing/reports/stage3-normalization-acceptance-2026-10-20.md). Проверены 543 теста (163 backend unit, 355 integration, 17 frontend, 8 browser); независимый retest — 106 backend и один browser, без открытых замечаний. Подробности проверок и нагрузки приведены в отчёте; финальный коммит и CI — в описании PR. Этап 3 не объединён и не объявлен принятым: для этого нужен зелёный CI merge commit в main. Matching не включён.

Для последующего импорта нужно согласовать первый pilot domain и формат реальной выгрузки 1С. Пороги matching остаются открытым решением; до его принятия нельзя молча вводить автоматическое объединение по fuzzy/embedding score.

## Известные расхождения спецификаций

План этапа 5 перечисляет `FORMAT` как Conflict type, а каноническая модель v0.2 — `VALUE_MISMATCH`, `MISSING`, `DUPLICATE`, `RULE_VIOLATION`, `ANOMALY`. План этапа 11 использует `FK_DEFAULT`, каноническая модель — `FK_BASELINE`. При реализации использовать канонические enum согласно AGENTS.md и Decision Log; новые enum без явного решения не вводить. На этап 0 эти расхождения не влияют.
