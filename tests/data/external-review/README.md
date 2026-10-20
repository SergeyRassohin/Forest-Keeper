# Открытый пример для внешней проверки: каталог событий USGS

Эти файлы позволяют проверить импорт и нормализацию без данных заказчика. Они содержат **60 реальных событий** магнитудой от 4 за 1 января 2025 из открытого USGS Earthquake Catalog. Это технический пример другого домена, не выбранный промышленный pilot domain и не benchmark качества matching.

Источник: [USGS query CSV](https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=2025-01-01&endtime=2025-01-02&minmagnitude=4&orderby=time-asc). [Документация API](https://earthquake.usgs.gov/fdsnws/event/1/). Получено 21 октября 2026; каталог может корректироваться, поэтому для воспроизведения используется сохранённый snapshot, а не новая выдача API.

Условия использования: [USGS Copyrights and Credits](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits). Использованы USGS-authored данные правительства США из публичного каталога (public domain), без сторонних изображений/вложений. Источник указан добровольно для проверяемости; этот пример не означает одобрение продукта USGS.

## Файлы и изменения

| Файл | Что содержит |
| --- | --- |
| usgs-original.csv | Неизменённый ответ API, 60 записей |
| source-a.csv | Проекция исходного ответа: id, name=place, magnitude=mag, occurred_at=time |
| source-b.xml | Те же 60 событий в generic XML; id переведены в верхний регистр, name — в нижний; добавлены окружающие пробелы |
| provenance.json | URL, дата, SHA-256 всех трёх файлов, описание изменений |

source-a/source-b — **две производные выгрузки одного источника**, не независимые наблюдения и не реальный межсистемный конфликт. Никакие магнитуды, времена или идентичности не выдуманы. В файлах нет синтетических конфликтов, маскируемых под исходные факты.

## Как проверить

1. Выполните [Quick Start](../../../docs/deployment/external-review-quickstart.md), создайте два источника типа FILE.
2. Загрузите source-a.csv в первый и source-b.xml во второй источник. Ожидается по 60 RawRecord, импорт COMPLETED.
3. Выберите профиль **public-earthquake v1** для обоих пакетов. Исходный usgs-original.csv этому профилю не соответствует: он хранится для provenance; его можно отдельно импортировать для просмотра raw, но не нормализовать этим mapping.
4. В каждом запуске ожидается 60 представлений × 4 атрибута = **240 VALID значений**. `code` — id в нижнем регистре; `name` — место в верхнем регистре без окружающих/повторных пробелов; magnitude — Decimal строка; occurred_at — исходная UTC-строка.
5. Для события `us6000pjr6` сравните: source-a имеет id `us6000pjr6`, source-b — `  US6000PJR6  `; normalized code одинаков. Магнитуда — `4.2`, время — `2025-01-01T00:13:22.650Z`.
6. Убедитесь, что source-b raw сохранил верхний регистр/пробелы. Равенство normalized values не должно переписать raw.
7. Перезапустите приложение без удаления volumes; найдите те же ImportBatch/AnalysisRun IDs и исходные значения.

Для единиц измерения/ошибочных значений есть отдельные **синтетические** fixtures в tests/data/normalization и профиль synthetic-material v1. Не применяйте его к каталогу событий.

Профиль public-earthquake — release configuration для демонстрации. Он не включает автоматическое назначение Authoritative Source, matching, Conflict, Decision или AI. Отсутствующие функции записываются как BLOCKED по [матрице готовности](../../../docs/deployment/review-readiness.md).
