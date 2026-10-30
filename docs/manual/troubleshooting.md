# Forest Keeper: ошибки и безопасная диагностика

[К содержанию](README.md) · [Установка](installation.md) · [Чеклист](walkthrough-checklist.md)

## Сначала соберите доказательства (без секретов)
Из корня `Forest-Keeper`:
```bash
git branch --show-current
git rev-parse HEAD
docker compose ps -a
docker compose logs --tail=100 migrate backend worker frontend
docker compose logs --tail=100 postgres redis
curl --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/health
```
Логи могут содержать названия файлов, адреса и значения. **Перед передачей обезличьте их**. Никогда не отправляйте `.env`, пароли, токены, cookies, TLS private keys, полные выгрузки предприятия и модельные артефакты.

| Симптом | Наиболее вероятная причина | Что делать безопасно |
|---|---|---|
| `docker: command not found` или `docker info` не работает | Docker Desktop/Engine не установлен, не запущен или WSL integration выключена | Запустить Docker Desktop, проверить интеграцию с Ubuntu, снова `docker info` |
| `docker compose` неизвестна | Нет Compose v2 | Установить Compose plugin/Desktop; не подменять команду неизвестным скриптом |
| `git clone` требует логин/404 | Нет сети, права на private repo или неправильный URL | Проверить ссылку, доступ GitHub и сеть; не публиковать токен |
| `port 8443 already allocated` | Порт занят | Найти и остановить конфликтующий локальный сервис; не удалять volumes |
| `migrate Exited (0)` | Нормальное одноразовое завершение | Ничего не исправлять |
| `migrate Exited (1)` или health 503 | Ошибка миграции, PostgreSQL/Redis ещё не готовы | Смотреть `docker compose logs migrate postgres redis backend`; не стирать БД ради миграции |
| `backend`/`worker` в Restarting | Ошибка конфигурации, очереди или зависимости | Просмотреть logs, убедиться в готовности postgres/redis и наличии `.env` |
| Ноутбук не открывает `https://PC_LAN_IP:8443` | Это ожидаемо: Compose слушает только loopback ПК, сертификат и Origin настроены под localhost | Использовать браузер на ПК или SSH-туннель по [инструкции](installation.md#дополнительно-доступ-с-ноутбука-в-домашней-сети); не открывать 8443 в интернет |
| С ноутбука через SSH-туннель ошибка соединения | SSH-сервер на ПК не настроен, 8443 занят на ноутбуке или SSH-сервер не видит loopback Docker | Проверить SSH и `localhost:8443` на ПК; сначала завершить базовый сценарий на основном ПК |
| Браузер не открывает страницу | Нет frontend, неверный адрес, занят порт, удалённый хост без туннеля | `docker compose ps -a`, `https://localhost:8443`, проверка SSH-туннеля |
| Предупреждение сертификата | Self-signed dev TLS | Разрешать **только на localhost**, не отключать глобально TLS; при истечении сертификата следовать проверенной процедуре перевыпуска, не удалять secrets/volumes наугад |
| Login 401 | Неверный пароль или нет аккаунта | Проверить учётную запись; bootstrap возможен только при пустой таблице пользователей |
| Login 403 / Origin | Неподходящий hostname для `FK_ALLOWED_ORIGINS` | Использовать `https://localhost:8443`, при внешнем доступе настроить разрешённый origin согласно auth docs |
| Login 429 | Лимит попыток | Выдержать интервал rate-limit, не штурмовать вход |
| Создание пользователя 403 | Сессия ADMIN не свежая | Выйти и снова войти, повторить в течение 5 минут |
| REVIEWER не видит кейс | Нет разрешённого domain scope | ADMIN должен явно выдать scope; проверять права, а не отключать авторизацию |
| Импорт остаётся QUEUED | Worker остановлен или Redis недоступен | `docker compose ps -a` и `docker compose logs --tail=100 worker redis`; не отправлять бесконечно одинаковые импорты |
| Файл отклонён/нет полей | Неподдержанный формат или нет подходящего mapping | Сначала проверить `tests/data/...`; generic XML != произвольный экспорт 1С; не выдавать FAIL парсинга за успешную обработку |
| Нет normalized fields | Выбран профиль другого домена | Выбрать совместимый `synthetic-material v1` для synthetic-material files |
| Пустые matching/Conflicts | Не те AnalysisRun, неверный профиль, анализ ещё идёт или scope | Сверить оба COMPLETED ID, профиль, статус анализа, войти REVIEWER с нужным scope |
| Сохранение Decision 409 | Кейс изменился в другой сессии | Обновить карточку, сверить evidence, повторить новый осмысленный выбор; без слепого POST |
| Similarity/Recommendation UNAVAILABLE | Production embedding/provider недоступен по design | Для `main` это **ожидаемое ограничение**, не повод отключать безопасность |
| Qwen не запускается | Stage 9 не входит в `main` | Для этого личного сценария **не требуется**; отдельный PR #33 не принят |

## Восстановление без потери истории
Если контейнеры нестабильны, сначала сохраните SHA и логи; дождитесь завершения активных операций. Затем:
```bash
docker compose stop -t 30 worker
docker compose restart postgres redis backend frontend
docker compose up -d --wait --wait-timeout 180 worker
```
Снова проверьте health и те же ImportBatch/Decision IDs. При полной остановке используйте `docker compose down` **без** `-v`, затем `docker compose up -d --wait --wait-timeout 180`.

**Запрещено как «быстрое исправление»:** `docker compose down -v`, `docker volume prune`, `git reset --hard`, удаление локальных конфигов, ручные правки БД, принудительное отключение auth, перезапись enterprise data.

## Что отправить разработчику
```text
Дата:
Windows/Linux/macOS и версия:
CPU / RAM:
Docker / Compose:
git SHA и ветка:
Номер шага из docs/manual/walkthrough-checklist.md:
Ожидалось:
Получилось:
PASS / FAIL / BLOCKED:
HTTP status / точный текст ошибки:
ID ImportBatch / AnalysisRun / Conflict / Decision (если есть):
Обезличенные логи (не .env, не пароли):
```
Если проблема только в отсутствии Qwen на `main`, помечайте **BLOCKED (Stage 9)**, а не «сломан импорт».
