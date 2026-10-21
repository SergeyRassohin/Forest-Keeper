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

На момент этапа 1 бизнес-модули ещё отсутствовали. Актуальный статус: импорт и нормализация приняты в этапах 2–3 ниже; matching, conflicts, Human Review, Decision Registry, AI/similarity, правила, лицензирование и Update Service в main пока отсутствуют. Продуктовый E2E решений и capacity/performance acceptance всего MVP предстоят.

## Приёмка этапа 1

Этап1 принят после полного независимого прогона [issue #5](https://github.com/SergeyRassohin/Forest-Keeper/issues/5), исправления WEB-02 и merge PR #6. Все35пунктов сценария PASS,245тестов и CI main прошли. Обновление CI Actions/runner принято через PR #4.

## Итерация 3 — этап 2

По [issue #7](https://github.com/SergeyRassohin/Forest-Keeper/issues/7) реализованы SourceSystem, ImportBatch, неизменяемый RawRecord, локальное persistent хранилище оригиналов, SHA-256 и фоновые jobs RQ. Добавлены защищённые source/import API, страницы ошибок/исходных записей, duplicate policy и явный retry новым пакетом, браузерный раздел «Импорт данных».

Форматы: UTF-8 CSV, первый worksheet XLSX, generic XML и документированный синтетический профиль 1С XML. Дополнительное ревью выявило четыре дефекта: CSV после потери границы записи, XLSX duration/специальные формулы, поздний enqueue и отмена медленных browser requests. Исправлены в `64afea2`, добавлены регрессии. Прогон исправлений до интеграции hardening: **393 backend (80 unit / 313 integration), 13 frontend и 7 browser — всего 413 PASS**, все security gates; независимый retest четырёх исправлений без открытых замечаний.

Capacity на исправленном runtime: два набора 100000×30 атрибутов, по 30000381 байт; обработаны за 20.818 и 20.174 сек, metadata p95=0.2263 сек при 10 сессиях. [PR #8](https://github.com/SergeyRassohin/Forest-Keeper/pull/8), [актуальный отчёт и exact-SHA CI](../testing/reports/stage2-import-review-fixes-2026-10-19.md), [Import subsystem](import.md). Первоначальные проверки `6380d5c` сохранены в [историческом отчёте](../testing/reports/stage2-import-acceptance-2026-10-19.md). Это исторический результат до синхронизации с production hardening; актуальный merge и итоговые проверки указаны ниже.

Этап 2 объединён в main через PR #8, merge commit `52de120`; [CI merge commit](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39415262127) прошёл. Вместе с hardening PR #10 проверены 408 backend (95 unit / 313 integration), 13 frontend и 7 browser — всего 428 PASS; production smoke включает общий том оригиналов. [Отчёт синхронизации](../testing/reports/stage2-main-sync-2026-10-20.md).

Этап 3 — нормализация и canonical model — реализован по [issue #12](https://github.com/SergeyRassohin/Forest-Keeper/issues/12) в [PR #13](https://github.com/SergeyRassohin/Forest-Keeper/pull/13): [описание](normalization.md), [acceptance report](../testing/reports/stage3-normalization-acceptance-2026-10-20.md). Проверены 543 теста (163 backend unit, 355 integration, 17 frontend, 8 browser); независимый retest — 106 backend и один browser, без открытых замечаний. Подробности проверок и нагрузки приведены в отчёте; финальный коммит и CI — в описании PR. Этап 3 принят и объединён: merge `6a494534a49960b79fdf64e5e2b8436c32011688`; [CI merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39452965438). Исторический acceptance report сохранён без переписывания. Следующий активный этап — 4, [draft PR #15](https://github.com/SergeyRassohin/Forest-Keeper/pull/15); matching ещё отсутствует в main.

Для последующего импорта нужно согласовать первый pilot domain и формат реальной выгрузки 1С. Пороги matching остаются открытым решением; до его принятия нельзя молча вводить автоматическое объединение по fuzzy/embedding score.

## Известные расхождения спецификаций

Устранены устаревшие enum в текущем MVP Plan: типы Conflict соответствуют v0.2 (`VALUE_MISMATCH`, `MISSING`, `DUPLICATE`, `RULE_VIOLATION`, `ANOMALY`), origin Rule — `FK_BASELINE`, а не `FK_DEFAULT`. Локальный вход описан как browser cookie session по решению 2026-10-19. Это синхронизация документации; runtime enum не менялись.


## Ближайшая контрольная цель — внешняя проверка

Ближайшая продуктовая цель: подготовить репозиторий и MVP к независимой проверке внешним техническим специалистом к **субботе, 24 октября 2026**.

Критерий готовности:

```text
GitHub читаем и понятен
→ все зависимости и ссылки живые
→ setup воспроизводим по инструкции
→ Web Client запускается
→ пользователь загружает собственные CSV/XLSX/XML
→ запускает анализ
→ получает осмысленный результат
→ при доступности Human Review сохраняет решение
→ формирует независимое мнение о продукте без помощи авторов
```

Основная реализационная задача: issue #18 — External MVP review readiness.

До прохождения этой проверки новые необязательные возможности не должны вытеснять работу по end-to-end сценарию, setup и документации.

## Документация внешней проверки — 21 октября 2026

Обновлены README, [Quick Start](../deployment/external-review-quickstart.md), серверные инструкции и описание моделей. [Матрица готовности](../deployment/review-readiness.md) перечисляет блокеры полного сценария #18. Зафиксированы открытые данные USGS с происхождением и отдельным демонстрационным normalization profile. Согласовано: fuzzy требует ручной проверки; авто-подтверждение только по согласованным точным ключам без противоречий. Проверка Qwen artifacts не означает наличие AI inference; независимое внешнее ревью этой правки ещё ожидается.

## Этап 4 — кандидат отдельной приёмки, 21 октября 2026

Первый шаг [issue #20](https://github.com/SergeyRassohin/Forest-Keeper/issues/20): существующий [PR #15](https://github.com/SergeyRassohin/Forest-Keeper/pull/15) синхронизирован с current main и PR #19. Runtime `6669d1c357f8bdf503013b31a1138de1269a0771`; текущий final HEAD и его CI указаны в PR. Реализованы [matching](matching.md), три статуса, immutable evidence/provenance, versioned profiles, bounded generation и авторизованный ручной review с причиной. Подтверждение идентичности не заменяет Decision Registry.

Локально **619 тестов PASS** (181 backend unit, 401 integration, 21 frontend, 10 HTTPS browser, 6 artifact tests), обязательные security/dependency gates и production smoke PASS. Gold: precision 1.0, recall 0.8, false merges 0; fuzzy auto-match отключён. Capacity: все профили 100/1k/10k/100k PASS, на 100k/source создано 100000 кандидатов вместо 10 миллиардов пар, matching 54.093 s, metadata p95 0.3648 s при 10 сессиях. После штатного restart неизменны run/evidence, два ручных review, raw и normalization history. [Отчёт, DoD и доказательства](../testing/reports/stage4-matching-acceptance-2026-10-21.md).

**Статус: BLOCKED для принятия/merge до отдельного independent runtime/security retest и подтверждения финального CI.** Исторический entry gate не заменяет этот retest. Автоматический merge запрещён; Stage 4 ещё не принят и отсутствует в main. Stage 5 не начат: по #20 он начинается после отдельной приёмки Stage 4, разрешённого merge и зелёного CI merge commit. Полная внешняя готовность #18 остаётся BLOCKED.
