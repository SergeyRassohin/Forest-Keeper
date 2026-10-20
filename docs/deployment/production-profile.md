# Worker readiness и отдельный production-профиль

Изменения по [задаче №9](https://github.com/SergeyRassohin/Forest-Keeper/issues/9).
`compose.yaml` остаётся окружением разработки. `compose.production.yaml` — самостоятельная
конфигурация усиления защиты; не объединяйте эти файлы через несколько `-f`.
Она покрывает этапы 0–2 (миграция 0003), включая общий том оригиналов импорта,
но не объявляет весь MVP готовым к промышленной эксплуатации. Новые этапы требуют проверки своих mounts и настроек.

## Состояние worker

`python -m app.worker_health` проверяет собственный RQ worker по hostname контейнера:
регистрацию в Redis, состояние `idle`/`busy`, наличие очереди и свежесть heartbeat.
Это два read-only запроса Redis без постановки заданий и изменения бизнес-данных.
Ошибки дают код 1 и сообщение `worker unavailable` без URL и traceback.
Для проверки другого контейнера доступен технический аргумент `--name HOSTNAME`.

Worker TTL — 120 секунд, обычное ожидание без заданий — до 105 секунд, допустимый возраст
heartbeat — 150 секунд. Compose проверяет каждые 10 секунд (timeout 5 секунд,
3 неудачи, startup grace 30 секунд). Зависание обнаруживается примерно через 150–180 секунд
после последнего heartbeat; недоступный Redis также делает probe неуспешным.
Статус `unhealthy` доступен через `docker compose ps` / `docker inspect` для мониторинга.
Compose сам не перезапускает зависший контейнер: `restart: unless-stopped` действует
при завершении процесса. Оповещение и реакцию оператора нужно подключить на сервере.

## Образы и локальные секреты

Соберите и проверьте образы заранее, загрузите их в Docker сервера. Профиль использует
`pull_policy: never`; облачный registry или vault для запуска не нужен.
Скопируйте [пример метаданных](../../deploy/production/environment.example) в
`/opt/forest-keeper/production.env`, задайте теги/дижесты и точный внешний HTTPS origin.
Файл метаданных не должен содержать пароли или database URL.

Создайте каталог `FK_PROD_SECRETS_DIR` с правами 0700 и файлами:

| Файл | Содержимое | Владелец UID:GID и права на обычном rootful Docker |
| --- | --- | --- |
| `postgres_password` | Случайный пароль PostgreSQL | 999:999, 0400 |
| `fk_database_url` | Полный `postgresql+psycopg://forest_keeper:<URL-encoded-password>@postgres:5432/forest_keeper` | 10001:10001, 0400 |
| `server.crt` | Сертификат HTTPS и необходимая цепочка | публичный сертификат, 0444 |
| `server.key` | Закрытый ключ HTTPS | 101:101, 0400 |

Создавайте файлы средствами защищённого provisioning, не передавайте содержимое через
аргументы shell или историю команд. Пароль в URL должен соответствовать первому файлу.
Секреты не включены в Git, образы или `Config.Env`: PostgreSQL читает `POSTGRES_PASSWORD_FILE`,
приложение — Pydantic file secrets из `/run/secrets/fk_database_url`.
Приоритет настроек сохранён: явные параметры → environment → dotenv → file secrets.
Не добавляйте credential environment overrides в production-конфигурацию.

В обычном Compose file secrets — read-only bind mounts: UID/GID/mode файла хоста сохраняются,
переназначение `uid`/`gid` в YAML не решает доступ. При rootless Docker/user namespaces
проверьте соответствие UID на целевом сервере. Не устраняйте ошибку доступа запуском от root.
Docker/host administrator всё равно может читать секреты; Compose не шифрует эти файлы.
Защита диска, резервных копий, ротация и хранение ключей остаются задачами эксплуатации.

```bash
docker compose --env-file /opt/forest-keeper/production.env -f compose.production.yaml config --quiet
docker compose --env-file /opt/forest-keeper/production.env -f compose.production.yaml up -d --wait --wait-timeout 180
docker compose --env-file /opt/forest-keeper/production.env -f compose.production.yaml ps
```

По умолчанию HTTPS доступен на 127.0.0.1:8443 для серверного reverse proxy.
Для прямого доступа настройте bind address, TLS, firewall и внешний origin совместно.
PostgreSQL, Redis и API не публикуют порты хоста. Nginx production config включён в образ,
TLS файлы доступны только nginx. Внутренний nginx healthcheck проверяет HTTPS без проверки
доверия сертификату; loopback probe явно отключает proxy только для этого локального запроса.
Внешний smoke отдельно проверяет сертификат с доверенным CA.

## Запись и ресурсы

Все процессы non-root, root filesystem read-only, capabilities сброшены, включён
`no-new-privileges`. Начальные лимиты требуют измерения на целевом сервере:

| Сервис | CPU / RAM / PID | Разрешённая запись и причина |
| --- | --- | --- |
| backend | 1 / 1 GiB / 128 | `/tmp` tmpfs 64 MiB; `import_files` для оригиналов; `upload_tmp` для multipart spooling |
| worker | 1 / 1 GiB / 128 | `/tmp` tmpfs 64 MiB; общий named volume оригиналов импорта |
| migrate | 1 / 1 GiB / 128 | `/tmp` tmpfs 64 MiB для временных файлов |
| PostgreSQL | 2 / 1 GiB / 256 | named volume PGDATA для БД; tmpfs socket directory 16 MiB и `/tmp` 32 MiB |
| Redis | 1 / 256 MiB / 64 | named volume `/data` для AOF; `/tmp` tmpfs 16 MiB |
| nginx | 0.5 / 128 MiB / 64 | `/tmp` tmpfs 32 MiB для PID и временных buffers; один worker |

Секреты монтируются read-only, остальные host writable mounts отсутствуют.
Не удаляйте named volumes при обновлении. До эксплуатации нужны процедуры backup/restore,
ротации, мониторинга и настройки DB privileges. Параметры ядра Redis (например,
`vm.overcommit_memory`) проверяет администратор; скрипты проекта настройки хоста не меняют.

## Воспроизводимая проверка

Обычный dev запуск остаётся `docker compose up --build --wait` после dev-init.
Для изолированной проверки на других портах integration script поддерживает `FK_ENV_FILE`
и `FK_E2E_BASE_URL`, по умолчанию использует прежние `.env` и localhost:8443.

```bash
python scripts/check-production.py --backend-image forest-keeper-backend --frontend-image forest-keeper-frontend
```

Скрипт создаёт собственный случайный Compose project, синтетические секреты и TLS,
проверяет HTTPS, реальное RQ задание, non-root/read-only и ресурсные лимиты.
Две одновременные HTTPS-загрузки ровно по 100000000 байт проверяют multipart, сохранение
оригиналов, точные SHA-256 и освобождение временных файлов; worker в это время остановлен,
поскольку тест загрузки не должен обрабатывать миллионы синтетических записей.
Останавливает только свой worker через SIGSTOP, искусственно старит технический heartbeat,
проверяет probe и фактический Docker `unhealthy`, затем stop/start и возврат `healthy`.
Проверяет сохранность тестовых значений PostgreSQL/Redis после restart и отсутствие
значений credentials в render config, container environment и логах.
В `finally` удаляет только свои контейнеры/volumes. Тестовые файлы имеют mode 0444 внутри
приватного каталога 0700 для разных container UID; это fixture, а не инструкция для реальных секретов.
Этот smoke включён в CI вместе с обычными тестами, SAST/SCA и secret scanner.

## Оригиналы Stage 2

Backend и worker используют общий named volume `import_files` по адресу
`FK_IMPORT_STORAGE_ROOT=/var/lib/forest-keeper/imports`. Это исключение для записи
нужно для сохранения загрузок и чтения тех же байтов worker. Образ готовит каталог
для UID/GID 10001; rootfs остаётся read-only. Сохраняйте и резервируйте том вместе
с PostgreSQL. Production smoke проверяет доступ из обоих сервисов и сохранность
байтов после restart. Nginx принимает до 101 MiB и передаёт upload без buffering,
как dev gateway; backend сохраняет собственный лимит и проверки загрузки.

## Временные загрузки

Multipart parser сначала полностью принимает файл во временное хранилище. Backend
использует отдельный дисковый named volume `upload_tmp` по адресу
`/var/lib/forest-keeper/upload-tmp`, UID/GID 10001, mode 0700, с `TMPDIR` только у backend.
Том создаётся отдельно от уже существующих оригиналов, поэтому обновление не требует
удаления или повторной инициализации `import_files`. Worker и migrate его не получают;
read-only rootfs и 64 MiB tmpfs `/tmp` сохранены. Dev flow не меняется.

Большие файлы больше не конкурируют за 64 MiB RAM-диска. При планировании свободного
диска учитывайте все параллельные uploads и временное одновременное хранение spool и
оригинала (до примерно 200 MB на запрос при лимите 100 MB), а также сохранённые оригиналы
и данные БД. Docker named volume не задаёт квоту диска; мониторинг свободного места
и ограничение входящей нагрузки остаются настройками сервера. Временные файлы закрываются
после запроса, при ошибке или disconnect; при завершении процесса ОС освобождает их.
Они не являются backup-данными. ENOSPC/EDQUOT при приёме/сохранении возвращает HTTP 507
`STORAGE_FULL` с безопасным сообщением вместо HTTP 500; неуспешный оригинал удаляется,
ImportBatch не создаётся. После освобождения места загрузку можно повторить.
