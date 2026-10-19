# Stage 2: независимая security-проверка — итог

Проверяющий: отдельный Codex agent `/root/independent_review`, не писавший реализацию. Проверка проведена 19.10.2026 по issue #7 и AGENTS.md («Security-critical changes require independent verification»). Проверялся незакоммиченный diff ветки `feat/stage2-import`; base HEAD `4efa434a4ee794d127bdd3b4e82f5afb19be16d3`.

**Итог независимого security review: все обнаруженные замечания исправлены и независимо перепроверены; открытых findings в проверенном snapshot нет.** Код приложения проверяющий не редактировал; GitHub-сообщения/публикации не выполнял.

## Охват

Прочитаны issue #7, AGENTS, canonical model/lifecycle, security/access matrix и Stage 2 runtime: imports storage/parsers/jobs/service/recovery/routes/models/schemas, migration 0003, backend wiring/config/worker, Docker/Compose/nginx и frontend Imports.

Проверены: filename/path safety, actual-byte checksum, exclusive original creation, size limits, multipart auth/CSRF, source/import RBAC, raw/origin immutability, duplicate concurrency, worker idempotency/recovery, XML entity defenses, XLSX ZIP and logical-resource limits, безопасное отображение raw content.

## Найденные дефекты и повторные проверки

### 1. Recovery перезаписывал завершённый пакет (исправлено)

`backend/app/imports/jobs.py`, исходный `recover_imports`: сначала ORM SELECT QUEUED/PROCESSING без общего worker lock, потом Redis lookup и transition на устаревшем объекте.

В isolated-schema probe `Job.fetch_many` подменён callback, который реально выполняет `execute_import` после первоначального SELECT: сначала COMPLETED с одним RawRecord, затем recovery возвращает 1 и записывает FAILED. Это нарушало terminal lifecycle.

Исправление: shared advisory key, lock и свежий row read; проверка свежести и terminal status. Независимый retest специально завершает worker между сканированием IDs и получением lock: recovery возвращает 0, пакет остаётся COMPLETED. Активный worker advisory lock также блокирует вмешательство recovery/failure callback; поздний failure callback не меняет COMPLETED.

### 2. Crash между NEW commit и enqueue оставлял вечный NEW (исправлено)

`backend/app/imports/routes.py` upload/retry фиксировали NEW до публикации; исходный `recover_imports` не рассматривал NEW, duplicate возвращал тот же NEW, retry запрещался. Это подтверждено исходным control flow; runtime probe успел загрузить уже исправленную реализацию.

Исправление: stale NEW восстанавливается разрешённым NEW→QUEUED, publication после release lock. Независимый isolated-schema retest: recovered=1, QUEUED, затем фактический execute_import даёт COMPLETED. Собственный RQ job/queue удалён.

### 3. Одна CSV NUL-запись ломала весь chunk (исправлено)

Repro bytes: `b'id,name\n1,Good\n2,Bad\x00value\n3,Good\n'`. До исправления JSONB отвергал NUL и результат был FAILED / loaded=0 / errors=0 / raw=0 вместо сохранения двух хороших записей.

Исправление parser bounded: PostgreSQL-safe JSON validation, без изменения raw values. Независимый retest: COMPLETED_WITH_ERRORS, loaded=2, errors=1, raw=2; ошибка INVALID_RAW_VALUE. Дополнительно проверены nested NUL и non-finite float NaN/Inf.

### 4. Длинный 1C XML Тип ломал весь chunk (исправлено)

Repro: три `<Объект>` в `<Выгрузка>`, у среднего атрибут Тип содержит 201 символ, у соседних нормальные Тип/Ид. До исправления VARCHAR(200) нарушался и весь chunk получал FAILED / 0 / 0 / 0.

Исправление: per-record INVALID_RAW_VALUE, без усечения исходного значения. Независимый retest: COMPLETED_WITH_ERRORS, loaded=2, errors=1, raw=2.

### 5. XLSX logical sparse-row bomb / OPC bypasses (исправлено)

Изначальный repro: valid.xlsx размером около 5.4 KB, в `xl/worksheets/sheet1.xml` заменить `<row r="3">` на `<row r="2000000000">`. ZIP guards проходили; openpyxl после первой записи пытался генерировать миллиарды пропущенных строк. Независимый subprocess остановлен timeout=3s; first-row marker уже был выведен. Worker занимался бы файлом до job timeout.

Первая версия исправления: streaming defused preflight worksheet XML, row/column/index/gap/depth bounds. Unit cases huge row, huge gap, XFD column, duplicate cell проходят (64 parser/storage/lifecycle tests passed).

**Но preflight выбирает лишь `xl/worksheets/*.xml`.** Openpyxl следует OOXML relationships: перенос entry в `xl/evil/sheet1.bin`, обновление workbook.xml.rels Target и [Content_Types].xml PartName оставляют workbook читаемым, но обходят preflight. Тот же huge row снова зависает после первой записи (5409 bytes, subprocess timeout=3s).

Следующая версия исправления проверила worksheet relationship targets независимо от пути/расширения: исходный и alias варианты стали отвергаться за 0.118/0.128 s; valid.xlsx сохранил 2 исходные записи; 65 unit tests прошли. Но ещё один обход подтверждён: изменить Type самого sheet relationship с /relationships/worksheet на /relationships/image. Preflight отбирает только worksheet Type, тогда как openpyxl читает все workbook sheet r:id relationships, кроме chartsheet. Alias .bin с таким Type снова зависает после first row (5414 bytes, timeout 3 s). Финальное исправление читает actual workbook из Content_Types и проверяет sheet r:id через workbook.rels, отказывает несогласованному Type, preflights все реально читаемые worksheet parts. Независимый subprocess retest всех трёх атак: UNSAFE_XLSX примерно за 0.1–0.15 s вместо timeout. Обычный valid.xlsx и нормальный relocated .bin workbook сохраняют две исходные записи, строку 001 и формулу =1+1. Финальный parser/storage/lifecycle unit: 66 passed. Silent truncation не применяется.

### 6. False IMPORT_FAILED log после terminal callback (исправлено)

DB-status после исправления пункта 1 сохранялся, но `fail_batch(completed)` всё равно писал IMPORT_FAILED, поскольку log_event находился за пределами условия transition. В recheck transcript это фактически наблюдалось. Логирование перенесено внутрь выполненного transition. Финальный isolated-schema assertion с mocked log_event подтвердил: поздний fail_batch(completed) не меняет terminal status и не пишет ложный IMPORT_FAILED.

## Дополнительные независимые результаты

- Parser/storage/lifecycle unit: первоначально 60 passed; после первого sparse fix — 64; финально 66 passed.
- Targeted source/import RBAC + raw/origin immutability: 56 passed, 19 deselected, 0 failed (отдельная временная schema).
- Own API probes: unauthenticated/Bearer-only upload 401; cookie mutations upload/source POST/PATCH/retry без Origin, с null/foreign — 403.
- Два concurrent identical uploads: 201/200, один ImportBatch, один сохранённый original, duplicate=True только во втором результате.
- XML XXE, internal entities, excessive depth отвергнуты; ошибки не содержали synthetic private marker/filesystem path.
- OOXML inner XXE также отвергнут; openpyxl DEFUSEDXML=True, LXML=False.
- ZIP traversal, VBA member, compression ratio и expanded-size cases отвергнуты как UNSAFE_XLSX.
- Filename никогда не используется как storage path; ключ UUID, exclusive create; checksum читается с сохранённых байтов; original read-only, raw DB-trigger append-only и origin metadata immutable.
- Frontend выводит raw payload/positions через React text, не innerHTML/eval; formulas не исполняются, data_only=False сохраняет formula text.

## Изоляция, ограничения, evidence

Только synthetic временные schemas/files и собственные RQ queues/jobs; shared worker не запускался и production data не затрагивались. Все собственные артефакты данных после probes очищены. Реальные credentials не выводились. Код приложения не изменялся.

Основной агент отдельно выполняет full Compose/RQ/browser/performance и обязательные gates; этот review не выдаёт их за самостоятельно выполненные. Проверяющий не заявляет full Stage 2 acceptance или pentest. Финальные независимые retests выполнены. Перед merge результат необходимо привязать к итоговому commit SHA и сохранить результаты полного CI/gates/functional/performance прогона, выполняемого основным агентом.

Sanitized evidence: `/tmp/fk-stage2-recheck.log`, `/tmp/fk-stage2-rbac-storage.log`, `/tmp/fk-stage2-csrf-duplicate.log`, `/tmp/fk-stage2-sparse-final.log`. Исходный probe-log содержит технический traceback ошибки подготовки собственного fixture, поэтому его не следует публиковать целиком; product repro/результаты выше отделены от harness ошибки.

Snapshot fingerprint: [independent-snapshot.json](independent-snapshot.json) содержит SHA-256 проверенных файлов, UTC и base HEAD; это незакоммиченный snapshot, а не заявление о проверке будущего commit.
