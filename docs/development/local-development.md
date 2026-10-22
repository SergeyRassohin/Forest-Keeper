# Локальная разработка MVP

Реализованы и приняты этапы 0–5: каркас, [Authentication + RBAC](authentication.md), [импорт](import.md), [нормализация](normalization.md), [matching](matching.md) и [Conflict Engine](conflicts.md). Human Review, Decision Registry и AI-рекомендации в main отсутствуют. Python 3.13, FastAPI/Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 17 + pgvector, Redis 7.4/RQ, React/TypeScript/Vite. Зависимости зафиксированы в `backend/uv.lock` и `frontend/package-lock.json`.

## Критерий готовности к внешней проверке

Помимо unit/integration checks, MVP должен проходить отдельный пользовательский acceptance-сценарий сторонним специалистом, который не участвовал в разработке:

```text
fresh clone
→ documented setup
→ Web Client
→ upload own CSV/XLSX/XML
→ analysis
→ human confirmation/correction
→ persisted Decision
→ restart without volume deletion
→ preserved history
```

После реализации AI-контура сценарий расширяется проверкой retrieval похожего подтверждённого Decision через pgvector и объяснением/рекомендацией, которая ссылается только на реально сохранённые evidence.

Подробная инструкция: [External MVP Evaluation & Server Setup](../deployment/server-installation-v0.1.md).

Этот acceptance-сценарий является продуктовым gate: прохождение отдельных API/unit tests не заменяет его.

## Запуск

Нужны Docker с Compose v2, Bash и OpenSSL. Из корня репозитория:

```bash
bash scripts/dev-init.sh
docker compose up --build -d --wait --wait-timeout 180
curl --fail --retry 15 --retry-connrefused --retry-delay 1 --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/health
```

Web Client доступен по `https://localhost:8443`. Локальный самоподписанный сертификат создаётся на 30 дней; браузеру нужно доверить этот сертификат. Скрипт не перезаписывает существующие `.env` и сертификаты. Для обновления истёкшего локального сертификата переместите оба файла из `deploy/local/tls/` и повторите инициализацию. Не используйте эти настройки как production deployment: локальная аутентификация уже реализована; корпоративный TLS требует отдельной настройки, лицензирование ещё отсутствует.

Compose сначала ждёт PostgreSQL/Redis, применяет миграцию, затем запускает API, RQ worker и Web Client. API и порты инфраструктуры доступны только через loopback. Данные сохраняются в named volumes; обычный `docker compose down` их не удаляет. Не используйте `down -v`, если данные нужно сохранить.

`GET /api/v1/health` возвращает 200 только при доступности PostgreSQL с текущей миграцией и pgvector, а также Redis; при недоступности — 503. Web Client показывает реальные состояния. `GET /api/v1/version` возвращает версию и текущий этап реализации только авторизованному пользователю с update.view (например ADMIN). Без cookie ожидается 401. Health не проверяет готовность ещё не реализованных бизнес-модулей или AI.

Для первого входа после запуска:

```bash
docker compose exec backend python -m app.auth.bootstrap --login admin --full-name "Администратор"
```

Пароль задаётся в скрытом приглашении (12–128 символов). Bootstrap доступен только при пустой таблице пользователей; стандартного пароля нет. Затем создайте пользователей с нужными ролями через Web Client. Полный [маршрут внешнего проверяющего](../deployment/external-review-quickstart.md) содержит ожидаемые результаты и примеры.

SQL-таймаут 500 мс задаётся через `SET LOCAL` только внутри транзакции health. Он не остаётся на pooled connection после завершения транзакции. Общий engine и Alembic используют обычную политику таймаутов PostgreSQL; миграции не ограничены этим health-таймаутом.

## Проверки

Для инструментов на хосте нужны Python 3.13, uv и Node.js 22–24:

```bash
cd backend
uv sync --frozen
cd ../frontend
npm ci
npx playwright install chromium
cd ..
bash scripts/check.sh
bash scripts/check-sast.sh
bash scripts/check-secrets.sh
bash scripts/test-security-gates.sh
bash scripts/check-dependencies.sh
bash scripts/check-integration.sh
```

На Linux для Playwright могут понадобиться системные библиотеки: `npx playwright install --with-deps chromium`. Проверка интеграции предполагает, что Compose уже запущен; она использует локальный `.env`, проверяет health, vector SQL, исполнение задания реальным RQ worker и открытие Web Client в Chromium. Не запускайте её против production.

`check.sh` также проверяет локальные Markdown targets и failure paths downloader (повреждение файла, неверный hash, размер и конкурентный partial). Для этих тестов uv получает закреплённый PyYAML 6.0.3; веса не скачиваются.

Security gates запускаются отдельно от lint/type checks. `check-sast.sh` выполняет Bandit для backend/app и миграций и ESLint security для frontend/src; любая находка или ошибка инструмента блокирует проверку. `check-dependencies.sh` выполняет SCA через pip-audit и npm audit. `check-secrets.sh` использует официальный Gitleaks v8.24.2 image, закреплённый по SHA-256 digest, и проверяет доступную историю всех Git refs плюс текущие tracked-файлы. На чистой машине Docker скачает image из `ghcr.io`. Для полного сканирования истории нужен полный checkout (в CI задан `fetch-depth: 0`). Перед локальным сканированием добавьте новые исходники в индекс; `.env`, TLS private keys и dependency caches должны оставаться вне Git. Найденные секреты маскируются в выводе; baseline и исключения для подавления находок не добавлены.

`test-security-gates.sh` создаёт временные синтетические примеры вне репозитория и проверяет отклонение shell injection, динамического eval и тестового PAT. Небезопасные примеры не исполняются. Скрипт проверяет именно код возврата находки и соответствующее правило, поэтому ошибка запуска scanner не считается успешным тестом. Скрипт очистит временные файлы после завершения.

Если Chromium уже установлен, можно использовать его без загрузки: `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium bash scripts/check-integration.sh`.

В облачной среде с HTTPS-прокси Docker может не разрешать имя прокси или не доверять его сертификату. Используйте `bash scripts/build-with-proxy.sh`, затем `docker compose up -d --wait --wait-timeout 180`. Адаптер передаёт DNS-сопоставление и системный CA bundle только на этапе сборки через BuildKit mount; сертификат не копируется в образ. Для корпоративного bundle задайте `FK_BUILD_CA_BUNDLE`. Проверка TLS сохраняется. В среде с read-only домашним каталогом задайте `DOCKER_CONFIG`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `npm_config_cache` в доступных каталогах; это настройки инструментов, а не приложение.

Unit-проверки явно исключают integration; integration без `FK_TEST_INTEGRATION=1` пропускается. Обязательный продуктовый E2E из плана MVP будет добавлен вместе с соответствующими этапами; `tests/e2e/foundation.spec.ts` проверяет только каркас.

Повторная проверка после перезапуска (сначала дождитесь завершения обработок; worker должен снять RQ-регистрацию до остановки Redis):

```bash
docker compose stop -t 30 worker
docker compose restart postgres redis backend frontend
docker compose up -d --wait --wait-timeout 180 worker
bash scripts/check-integration.sh
```

Дождитесь ответа health 200 после перезапуска зависимостей. Текущий migration head main — `0006_conflicts`; миграции 0002–0004 создают auth/import/normalization таблицы; 0005 добавляет matching runs/candidates, не переписывая Stage 2/3 историю; 0006 добавляет immutable conflicts и технические runs/inputs/outputs. Миграция `0001_foundation` включает pgvector. Alembic downgrade до base убирает запись версии, но сохраняет расширение для защиты зависимых объектов. Повторный upgrade восстанавливает готовность.

## Разработка без пересборки контейнеров

Этап2 добавляет persistent volume `import_files`, общий для backend и worker; обычный restart сохраняет оригиналы и PostgreSQL history. Не удаляйте volumes при обновлении. На хосте файлы пишутся в игнорируемый backend/var/imports (или FK_IMPORT_STORAGE_ROOT). Для обработки host-загрузок запускайте worker с тем же filesystem path и DB/Redis environment: `uv run --frozen python -m app.worker` из backend. Docker worker не видит произвольный host-каталог без общего mount. Форматы, лимиты, retry/recovery и отдельный capacity profile: [Import subsystem](import.md).

Поднимите PostgreSQL/Redis через `docker compose up -d postgres redis`, установите зависимости, экспортируйте переменные из локального `.env`, затем:

```bash
set -a
source .env
set +a
cd backend
uv run --frozen alembic upgrade head
FK_ALLOWED_ORIGINS='["https://localhost:5173"]' uv run --frozen uvicorn app.main:app --reload
```

Во втором терминале — `cd frontend && FK_VITE_HTTPS=1 npm run dev`; Vite использует локальный сертификат и проксирует /api на loopback backend. HTTPS нужен для session cookie. Браузерный smoke-тест полного контура использует HTTPS gateway из Compose.

## Документация, ссылки и модели

```bash
python3 scripts/check-doc-links.py
python3 scripts/check-doc-links.py --external --report work/link-check.json
uv run --script scripts/models.py check-upstream
```

Первая проверка локальная, вторая требует Интернет и сохраняет HTTP-результаты; model check сверяет pinned metadata/контрольные суммы, не запускает inference. Для полного получения весов и проверки локальных SHA-256 используйте [инструкцию Qwen](../ai/model-downloads.md). Модели не нужны для этапов 0–5.
