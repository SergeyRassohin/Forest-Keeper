# PR #8: независимый retest исправлений

Проверяющий: отдельный agent /root/independent_review; реализацию и исправления не писал.
Проверен рабочий diff поверх ddcebca33eb83a5aad9a3cd33f4499f9c93a146f (не будущий commit).

Итог: открытых замечаний по четырём проверенным исправлениям нет.

Реально выполнено:
- Собственный исходный late-enqueue reproducer, actual isolated PostgreSQL schema + отдельная RQ queue и настоящий SimpleWorker: recovery/worker завершили NEW, поздний исходный enqueue сохраняет COMPLETED, RQ finished, queue count 0 и RawRecord UUID. До исправления этот же сценарий возвращал QUEUED и повторную публикацию.
- Parser/storage/lifecycle unit: 72 passed. Включены потерянная multiline CSV boundary, positive/negative duration и ArrayFormula/DataTableFormula, реальные XLSX save/load.
- Focused integration regressions на временной schema/queue: 12 passed, 79 deselected. Broken CSV сохраняет только достоверный prefix и позицию fatal error; typed XLSX импортирует все три записи; late enqueue проверен для всех non-NEW статусов, shared lock, concurrent publication и actual RQ completion.
- Frontend Imports unit: 4 passed. В том числе metadata появляется до завершения raw fetch; raw request 2500 ms не отменяется polling; navigation отменяет старую загрузку и не показывает старые raw в новом batch.

Прочитан актуальный diff jobs/parsers/UI и соответствующих regression tests. enqueue использует общий advisory lock, fresh SELECT populate_existing и публикует только NEW после commit/release. CSV csv.Error больше не возобновляет чтение с неизвестной record boundary, ParseFailure сохраняет source position. Типизированные XLSX значения представлены JSON-структурой без исполнения формул. UI запускает следующий polling после завершения текущего набора запросов; metadata отображается отдельно.

Evidence без секретов:
- /tmp/fk-stage2-fixed-enqueue-race.log
- /tmp/fk-stage2-four-fixes-integration.log
- parser и frontend test results в tool transcript этого retest.

Ограничения: это targeted retest/read-only review; полный CI, пересобранный browser E2E и performance profile здесь не выполнялись. Новых security-исследований не проводилось. Собственные schemas/queues/files очищены, общие сервисы не останавливались. App/source, документация репозитория и GitHub проверяющим не изменялись.

Snapshot fingerprints:
- backend/app/imports/jobs.py: c94f819d9565cfd6be8d12f26201839c9ad46e23f3c53117a93edfa350fd9138
- backend/app/imports/parsers.py: a26cbbad2b247780d678f840e3a4350c16e5fae7c75159b5e2ad41a1db2bc703
- frontend/src/Imports.tsx: f004a337b7dc98c91d731b7738e4fa668b4432bc0e58e4f435c556d50ff32396

Checked UTC: 2026-10-19T20:27:47.583706+00:00
