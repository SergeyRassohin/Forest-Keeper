# Forest Keeper — External Reviewer Quick Start

Назначение: пошаговая инструкция для независимой технической проверки MVP человеком, который впервые видит Forest Keeper.

> Инструкция описывает только реально поддерживаемый путь. Если шаг ещё не автоматизирован или функция не реализована, это должно быть указано явно.

## 1. Что вы проверяете

Цель — пройти один рабочий пользовательский путь:

~~~text
fresh clone
→ запуск Forest Keeper
→ загрузка собственного CSV/XLSX/XML
→ обработка/анализ
→ просмотр provenance/evidence
→ подтверждение или исправление решения
→ сохранение Decision
→ перезапуск
→ проверка сохранности истории
→ второй похожий кейс
→ использование ранее подтверждённого решения как контекста
~~~

## 2. Что установить заранее

Обязательно: Git, Docker, Docker Compose v2, Bash, OpenSSL, современный браузер.

Проверка:

~~~bash
git --version
docker --version
docker compose version
bash --version
openssl version
~~~

Для обычной внешней проверки Python, uv и Node.js на хосте не нужны, если сценарий полностью запускается через Docker Compose.

## 3. Получение проекта

~~~bash
git clone https://github.com/SergeyRassohin/Forest-Keeper.git
cd Forest-Keeper
git rev-parse HEAD
git status
~~~

Сохраните commit SHA, который проверяете. Он понадобится для отчёта.

## 4. Первичная инициализация

Из корня репозитория:

~~~bash
bash scripts/dev-init.sh
~~~

Скрипт должен подготовить локальный .env и development TLS.

## 5. Запуск Forest Keeper

~~~bash
docker compose up --build -d --wait --wait-timeout 180
docker compose ps
~~~

Обязательные сервисы не должны быть в состоянии Exited или постоянного Restarting.

## 6. Проверка backend

~~~bash
curl --fail --retry 15 --retry-connrefused --retry-delay 1 --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/health
curl --fail --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/version
~~~

Если health не проходит:

~~~bash
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 worker
docker compose logs --tail=200 postgres
docker compose logs --tail=200 redis
~~~

## 7. Открытие Web Client

Откройте https://localhost:8443

Development-сертификат самоподписанный, поэтому браузер может потребовать явного доверия сертификату.

Проверьте, что Web Client открывается, API доступен и нет бесконечной загрузки.

## 8. Проверка импорта на собственном файле

Используйте минимум один собственный файл, который раньше не входил в fixtures Forest Keeper.

Желательно проверить: простой XLSX, XML и файл с дублями/конфликтами/неоднозначными значениями.

Поддерживаемые форматы MVP: CSV, XLSX, XML.

В интерфейсе:

1. создать или выбрать источник;
2. загрузить файл;
3. дождаться окончания import;
4. открыть результат;
5. проверить сохранение исходного файла и provenance;
6. убедиться, что нормализованные значения можно сопоставить с исходными.

Если import падает, зафиксируйте формат, размер, сообщение интерфейса, relevant backend/worker logs и commit SHA.

## 9. Проверка анализа и Human Review

Для данных, где есть потенциальные совпадения или конфликты:

1. открыть результат анализа;
2. проверить предложенное совпадение или конфликт;
3. проверить evidence;
4. подтвердить, исправить или отклонить решение;
5. сохранить действие;
6. зафиксировать ID Decision или объекта результата.

Критерий: действие пользователя должно стать отдельным сохраняемым Decision, а не только изменить состояние интерфейса.

## 10. Проверка сохранения истории

Без удаления volumes:

~~~bash
docker compose restart
~~~

После восстановления health снова откройте Web Client и найдите созданный Decision.

Дополнительно можно проверить полный stop/start:

~~~bash
docker compose down
docker compose up -d --wait --wait-timeout 180
~~~

Не выполняйте docker compose down -v. Эта команда удаляет persistent volumes и уничтожает историю, которую мы как раз проверяем.

## 11. Проверка памяти решений

Подготовьте второй кейс, похожий на уже подтверждённый.

Ожидаемая логика:

~~~text
confirmed Decision
→ structured context
→ embedding
→ pgvector
→ retrieval похожего Decision
→ recommendation/explanation context
~~~

Проверьте, что система находит релевантный прошлый Decision, показывает evidence, не выдумывает несуществующие решения и оставляет финальное решение человеку.

## 12. Qwen / AI-контур

Baseline проекта:

- LLM: Qwen/Qwen3-8B-GGUF;
- artifact: Qwen3-8B-Q4_K_M.gguf;
- embeddings: Qwen/Qwen3-Embedding-0.6B.

Точные revisions берутся только из models/model-manifest.yaml. Описание — docs/ai/local-model-v0.1.md.

Весовые файлы в Git не хранятся.

Проверяющий не должен вручную угадывать URL модели, revision, artifact, каталог или runtime command.

Для issue #18 требуется отдельный поддерживаемый bootstrap-script/command, который скачивает pinned artifacts, проверяет их и запускает AI services.

Пока такого bootstrap нет, AI-enabled часть внешнего review считается НЕ ГОТОВОЙ. Это не повод давать человеку ручной квест из десяти команд.

## 13. Что проверить в AI после реализации bootstrap

1. запустить AI services;
2. проверить AI health;
3. проверить model-info;
4. сверить model ID и revision с manifest;
5. выполнить похожий кейс с ранее подтверждённым Decision;
6. убедиться, что recommendation ссылается только на реально переданное backend evidence;
7. остановить LLM и убедиться, что deterministic review и Decision Registry продолжают работать.

Qwen не является базой памяти и не переобучается после каждого решения пользователя.

## 14. Минимальный отчёт проверяющего

~~~text
Commit:
OS:
Docker version:
Scenario:
Input file:
Expected:
Actual:
Error/log excerpt:
Severity: blocker / major / minor / suggestion
~~~

Отдельно полезно оценить понятность установки, UX, объяснимость результата, provenance/evidence, matching/conflict detection, сохранность истории, полезность AI и архитектурные риски.

## 15. Когда проверка успешна

Внешний специалист без помощи авторов проекта может:

- клонировать репозиторий;
- запустить Forest Keeper по инструкции;
- загрузить собственный файл;
- получить осмысленный результат;
- принять или исправить решение;
- перезапустить систему;
- найти сохранённое решение;
- пройти второй похожий кейс;
- понять, какие данные и evidence привели к результату.

Если для этого приходится писать разработчику «а какую команду здесь запускать?», инструкция или продукт ещё не готовы.