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
- 2 integration-теста: реальный PostgreSQL/vector SQL и задание в RQ worker;
- 1 Playwright smoke-тест Web Client → HTTPS → API → PostgreSQL/Redis;
- lint, форматирование Python, mypy, TypeScript (включая E2E), production build;
- контейнерные сборки и запуск, перезапуск всех runtime-сервисов и повторная integration/E2E-проверка;
- Alembic downgrade → health 503 → upgrade → health 200, повторный upgrade;
- `pip-audit` и `npm audit`: известных уязвимостей не обнаружено после обновления Vitest до исправленной версии. Собственный editable backend проверяется тестами и статическими анализаторами, а не каталогом уязвимостей сторонних пакетов.

Команды: [локальная разработка](local-development.md). CI workflow добавлен; успешный запуск GitHub Actions отдельно ещё не подтверждён.

Это завершённый этап 0, а не готовый продуктовый MVP. Нет auth/RBAC, импорта, canonical/matching/conflicts, Human Review, Decision Registry, AI/similarity, правил, бизнес-аудита, лицензирования и Update Service. Модели не скачивались. Главный двухитерационный продуктовый E2E, RBAC-тесты и capacity/performance acceptance всего MVP пока не выполнялись.

## Следующая итерация

Этап 1: User/UserRole, локальный login, безопасный password hash, session/access token, backend RBAC и клиентская авторизация. Права брать из XLSX-матрицы, а не из имён ролей; ADMIN не получает право бизнес-решения автоматически. Security-critical изменения требуют независимой проверки по AGENTS.md.

Для последующего импорта нужно согласовать первый pilot domain и формат реальной выгрузки 1С. Пороги matching остаются открытым решением; до его принятия нельзя молча вводить автоматическое объединение по fuzzy/embedding score.

## Известные расхождения спецификаций

План этапа 5 перечисляет `FORMAT` как Conflict type, а каноническая модель v0.2 — `VALUE_MISMATCH`, `MISSING`, `DUPLICATE`, `RULE_VIOLATION`, `ANOMALY`. План этапа 11 использует `FK_DEFAULT`, каноническая модель — `FK_BASELINE`. При реализации использовать канонические enum согласно AGENTS.md и Decision Log; новые enum без явного решения не вводить. На этап 0 эти расхождения не влияют.
