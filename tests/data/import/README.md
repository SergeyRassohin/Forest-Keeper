# Синтетические fixtures импорта

Ожидаемые количества RawRecord/errors, финальные статусы и примеры provenance заданы в manifest.json. Данные вымышленные, без credentials или выгрузок заказчика.

valid.csv сохраняет quoted comma/newline, пробелы и ведущие нули; duplicate.csv побайтно совпадает. valid.xlsx содержит первый лист Data, строковую формулу без вычисления, typed number и пустую строку; второй лист игнорируется. valid.xml соответствует generic records/record, onec.xml — тестовому профилю Выгрузка/Объект из import.md. partial.csv/xml сохраняют корректные объекты рядом с ошибками.

xxe.xml, entities.xml, unsafe.xlsx и corrupt.xlsx — отрицательные security/corruption fixtures. Никакое вредоносное содержимое не исполняется; внешняя ссылка использует example.invalid. Небезопасные имена и logical XLSX row/column bombs генерируются в unit/integration tests без чтения локальных секретов.

Для100/1000/10000/100000записей×30атрибутов: `backend/.venv/bin/python scripts/generate-import-data.py /tmp/source.csv --count 100000 --seed 42`. Большие generated datasets не коммитятся. Benchmark выполняется отдельно, с собственной временной schema/очередью/хранилищем, согласно docs/development/import.md.
