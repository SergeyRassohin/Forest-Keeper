# Этап 2: закрытие замечаний дополнительного ревью

[PR #8](https://github.com/SergeyRassohin/Forest-Keeper/pull/8), [ТЗ #7](https://github.com/SergeyRassohin/Forest-Keeper/issues/7). Дополнительное ревью `ddcebca33eb83a5aad9a3cd33f4499f9c93a146f` обнаружило четыре воспроизводимых дефекта, отсутствовавших в первоначальных тестах. Исправления: **64afea23b150273085d3b6544be18da144028b4b**. Дата: 19 октября 2026, Europe/Moscow; timestamps логов — UTC.

## Замечания и результат

| Finding | До исправления | Исправление и проверка |
|---|---|---|
| P1 CSV boundary | После csv.Error на поле свыше 1000000 символов строка внутри quoted value становилась ложным RawRecord. | Parsing прекращается с INVALID_CSV_STRUCTURE и source position. Ранее корректно прочитанный prefix сохраняется; фрагменты поля и оставшийся непроверенный suffix не импортируются. Unit проверяет oversized multiline и незакрытые кавычки; PostgreSQL/API regression подтверждает FAILED, один достоверный raw и одну ошибку. Оригинал побайтно прежний. |
| P2 XLSX typed values | Duration и ArrayFormula не сериализовались в JSON: корректный файл из трёх строк завершался FAILED после первой. | Duration хранит days/seconds/microseconds, включая отрицательные значения. ArrayFormula/DataTableFormula сохраняют тип/attributes, array — также исходный formula text. Реальные workbook save/load и DB/API tests подтверждают COMPLETED, 3 raw, 0 errors; вычисления формул нет. |
| P2 late enqueue | Задержанный upload после recovery/успешного RQ worker записывал cached NEW как QUEUED и публиковал завершённый batch повторно. | Общий advisory lock, свежий SELECT с populate_existing, переход/публикация только из NEW. Проверены все пять non-NEW статусов, отсутствие новых audit events/jobs, конкурентные enqueue и занятый worker lock. Исходный независимый real-RQ repro сохраняет COMPLETED, RQ finished и raw UUID. |
| P2 UI polling | Tick каждые 2 секунды отменял raw request длительностью 2.5 секунды; карточка не появлялась. | Metadata отображается отдельно; следующий poll планируется после завершения текущих запросов. Навигация отменяет старые запросы и очищает старые raw/errors. Unit fake-clock/AbortSignal и реальный HTTPS browser с задержкой records 2500 ms подтверждают открытие карточки и исходных значений. |

При повреждённой структуре CSV остановка является намеренным безопасным результатом: для обработки оставшихся строк нужно исправить исходный файл и загрузить его заново. Ошибки числа колонок с достоверной границей по-прежнему дают partial errors, сохраняя остальные записи. Подробная сериализация XLSX и polling описаны в [Import subsystem](../../development/import.md).

## Проверки

На runtime SHA выше пройдены **413 тестов, 0 failed**:

- 393 backend: **80 unit + 313 integration/API**;
- **13 frontend**;
- **7 HTTPS browser E2E**, включая два источника, duplicate/partial errors и новый медленный records response.

Добавлены 18 backend и 2 frontend regressions; существующий browser import-сценарий расширен. Проверки выполнены после пересборки контейнеров. Пройдены все шесть обязательных gates: `check.sh`, `check-integration.sh`, `check-sast.sh`, `check-dependencies.sh`, `check-secrets.sh`, `test-security-gates.sh`. SAST/SCA/secrets — без находок; отрицательные scanner fixtures отклонены. В integration-логе есть upstream warnings Starlette TestClient/httpx и Pydantic alias при конкурентной генерации app schema; тестовых ошибок нет.

Exact-runtime-SHA GitHub Actions [PR run](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39319574555) — **SUCCESS**. Дополнительный [push run](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39319566069) относится к тому же runtime SHA. После добавления отчёта отдельно проверяется актуальный HEAD PR; результаты доступны в checks PR.

Логи и fingerprints: [evidence](stage2-import-fixes-2026-10-19/). Первоначальные acceptance/gates остаются в [историческом отчёте](stage2-import-acceptance-2026-10-19.md) и не выдаются за повторную проверку нового кода.

Capacity profile повторён на исправленном runtime: два source dataset по **100000 записей × 30 атрибутов, 30000381 байт**, upload→реальный RQ→RawRecord: **20.818 и 20.174 секунды**, COMPLETED. Metadata API: **100 запросов / 10 одновременных сессий, p95=0.2263 с**, baseline ≤1 с выполнен. Как и первоначальный профиль, это ASGI/TestClient с реальными PostgreSQL/Redis/RQ без сетевой задержки gateway. Большие наборы, временная schema/очередь/файлы после прогона очищены; [результаты и hashes логов](stage2-import-fixes-2026-10-19/evidence.json).

## Независимая повторная проверка

Отдельный `/root/independent_review`, не писавший исправления, проверил diff и лично выполнил исходный real-RQ late-enqueue repro, **72 parser/storage/lifecycle unit**, **12 целевых DB/RQ tests** и **4 frontend Imports tests**. Открытых замечаний в scope четырёх исправлений нет. Проверяющий не выполнял полный browser/CI/performance и не приписывает себе эти результаты. Собственные temporary schemas/queues/files очищены. [Итог и SHA-256 проверенных runtime-файлов](stage2-import-fixes-2026-10-19/independent-review.md).

Роли, permissions, lifecycle, оригиналы, schema revision и границы Этапа 2 сохранены. Синтетический 1С XML и документированные parser/UI limits остаются прежними; нормализация и последующие этапы не добавлялись. После зелёного актуального CI PR готов к повторному ревью; merge и принятие выполняются отдельно.
