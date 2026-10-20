# Forest Keeper — External MVP Evaluation & Server Setup v0.2

Статус: инструкция для внешней технической проверки текущего MVP.  
Это **не** описание готового production installer. Автоматический корпоративный установщик, лицензирование и полностью offline-дистрибутив относятся к последующим этапам.

## 1. Цель внешней проверки

Проверяющий, не участвовавший в разработке Forest Keeper, должен без помощи авторов проекта:

1. клонировать репозиторий;
2. развернуть текущий MVP по документации;
3. открыть Web Client;
4. загрузить собственный файл поддерживаемого формата;
5. получить осмысленный результат обработки;
6. подтвердить, исправить или отклонить доступные пользователю решения;
7. убедиться, что подтверждённые решения сохраняются и могут использоваться системой в последующих похожих случаях;
8. зафиксировать замечания по архитектуре, UX, качеству анализа и воспроизводимости.

Ключевой критерий: проверяется **рабочий вертикальный сценарий**, а не только архитектура, API или набор отдельных модулей.

## 2. Что входит в границу MVP

Для внешней проверки MVP должен поддерживать сквозной путь:

```text
CSV / XLSX / XML
→ import + immutable raw/provenance
→ normalization / canonical representation
→ matching / conflict detection
→ human review
→ saved Decision
→ retrieval of relevant confirmed Decisions for later similar cases
→ explainable result
```

Не требуется для этой проверки:

- прямое подключение к Siemens NX, Teamcenter, SAP и другим корпоративным системам;
- автоматическая синхронизация с внешними источниками;
- production-grade SSO/IdP;
- готовый корпоративный installer;
- полноценный Forest Codex runtime/versioning;
- enterprise HA/DR;
- Desktop Client.

Если часть сквозного сценария ещё не реализована в текущей ветке, это должно быть явно указано в README/status документации. Заглушка не считается выполненной функцией.

## 3. Требования к машине проверяющего

Минимально нужны:

- Git;
- Docker с Compose v2;
- Bash;
- OpenSSL;
- современный браузер.

Для локального запуска инструментов разработки дополнительно нужны Python 3.13, uv и Node.js 22–24.

Требования к CPU/RAM/GPU для AI-контура должны проверяться отдельно в соответствии с используемым model manifest. Наличие GPU желательно для комфортной работы LLM, но архитектура не должна делать сохранение Decision Registry зависимым от доступности LLM.

## 4. Получение исходников

```bash
git clone https://github.com/SergeyRassohin/Forest-Keeper.git
cd Forest-Keeper
```

Используйте ветку/commit, явно указанные автором как кандидат для внешней проверки. Не подменяйте pinned модели или зависимости версиями `latest`.

## 5. Базовый запуск приложения

Из корня репозитория:

```bash
bash scripts/dev-init.sh
docker compose up --build -d --wait --wait-timeout 180
curl --fail --retry 15 --retry-connrefused --retry-delay 1 \
  --cacert deploy/local/tls/dev.crt \
  https://localhost:8443/api/v1/health
```

Web Client:

```text
https://localhost:8443
```

Локальный сертификат самоподписанный. Для тестовой машины его нужно явно доверить в браузере/ОС.

Обычный `docker compose down` сохраняет данные в named volumes.  
Не используйте `docker compose down -v`, если хотите проверить сохранение решений после перезапуска.

## 6. Локальный AI

Forest Keeper использует две отдельные локальные модели:

- LLM: `Qwen/Qwen3-8B-GGUF`, artifact `Qwen3-8B-Q4_K_M.gguf`;
- embeddings: `Qwen/Qwen3-Embedding-0.6B`.

Точные repository revision, artifact и runtime задаются в:

- `docs/ai/local-model-v0.1.md`;
- `models/model-manifest.yaml`.

Весовые файлы **не хранятся в Git**.

Важно: Qwen не является памятью Forest Keeper и не переобучается после каждого пользовательского решения.

Корпоративная память хранится в приложении:

```text
Human Decision
→ Decision Registry
→ structured context
→ embedding
→ PostgreSQL / pgvector
→ retrieval of similar confirmed Decisions
→ recommendation / explanation context
```

Таким образом после исправления пользователем результата должна сохраняться Decision-запись. При следующем похожем случае система может использовать эту запись как подтверждённый исторический контекст.

### Требование к удобству развёртывания AI

До внешней проверки репозиторий должен содержать поддерживаемый способ:

1. скачать **только pinned** модель и revision из `model-manifest.yaml`;
2. проверить artifact/checksum;
3. разместить модели в ожидаемых runtime-каталогах;
4. запустить LLM и embedding services;
5. выполнить smoke test;
6. показать точные model ID/revision через health/model-info.

Проверяющий не должен вручную угадывать URL, имена файлов, каталоги или версии моделей.

Если этот bootstrap ещё не реализован, внешняя проверка AI-контура считается заблокированной, а это ограничение должно быть явно указано в README.

## 7. Проверка на собственных данных

Проверяющий должен использовать хотя бы один собственный тестовый файл в поддерживаемом формате:

- CSV;
- XLSX;
- XML.

Файл не должен требовать предварительной ручной модификации под внутренние fixture проекта, кроме явно описанного mapping/setup шага.

Минимальный ожидаемый пользовательский цикл:

1. создать/выбрать источник;
2. загрузить файл;
3. дождаться завершения import/normalization;
4. открыть найденные совпадения, конфликты или результаты анализа;
5. проверить provenance и исходные значения;
6. подтвердить или исправить доступное решение;
7. убедиться, что Decision сохранён;
8. перезапустить приложение без удаления volumes;
9. убедиться, что сохранённая история не исчезла;
10. при наличии второго похожего случая проверить, что прошлое подтверждённое решение находится как релевантный контекст.

## 8. Что считать успешной внешней проверкой

MVP считается пригодным для содержательного технического review, если сторонний специалист без помощи разработчиков может пройти путь:

```text
clone
→ setup
→ start
→ upload own file
→ analysis
→ human correction/confirmation
→ persisted decision
→ restart
→ preserved history
```

Для AI-enabled review добавляется:

```text
→ retrieve similar confirmed decision
→ recommendation/explanation references real stored evidence
```

Красивый UI без рабочего persistence не проходит критерий.  
Архитектурная схема без запускаемого вертикального сценария тоже не проходит критерий. Люди и так производят достаточно PowerPoint, Forest Keeper не обязан увеличивать статистику.

## 9. Диагностика

Базовые проверки:

```bash
docker compose ps
curl --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/health
curl --cacert deploy/local/tls/dev.crt https://localhost:8443/api/v1/version
```

Полная локальная проверка разработчика описана в:

`docs/development/local-development.md`

AI baseline:

`docs/ai/local-model-v0.1.md`

Импорт:

`docs/development/import.md`

Нормализация:

`docs/development/normalization.md`

## 10. Будущий production deployment

Для production/on-prem поставки планируется отдельный установочный путь с:

- preflight checks;
- корпоративным TLS;
- offline AI bundle;
- signature/checksum verification;
- лицензированием;
- backup/restore;
- production health/readiness;
- IdP/SSO;
- upgrade/rollback.

Этот раздел не должен использоваться как доказательство наличия уже реализованного installer.
