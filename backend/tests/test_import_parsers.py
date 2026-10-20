import hashlib
import io
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from app.common.errors import ApiError
from app.imports.models import ImportBatch, ImportStatus
from app.imports.parsers import ParseFailure, check_xlsx, parse_records
from app.imports.service import TRANSITIONS, transition
from app.imports.storage import LocalStorage, checked_filename, file_checksum

DATA = Path(__file__).resolve().parents[2] / "tests/data/import"
MANIFEST = json.loads((DATA / "manifest.json").read_text())


@pytest.mark.parametrize("name", [name for name in MANIFEST if name != "unsupported.txt"])
def test_synthetic_parser_contract(name):
    expected = MANIFEST[name]
    rows, errors = [], []
    try:
        for item in parse_records(
            DATA / name,
            Path(name).suffix[1:].upper(),
            expected.get("source_type", "FILE"),
            512_000_000,
        ):
            (errors if item.error_code else rows).append(item)
    except ParseFailure as error:
        assert expected["status"] == "FAILED"
        assert error.message and "/" not in error.message
        errors.append(error)
    assert len(rows) == expected["records"]
    assert len(errors) == expected["errors"]
    if "first_position" in expected:
        assert rows[0].position.items() >= expected["first_position"].items()


def test_original_values_and_quoted_multiline_csv():
    rows = list(parse_records(DATA / "valid.csv", "CSV", "FILE", 512_000_000))
    assert rows[0].payload == {"id": "001", "name": "Болт, сталь", "price": "001.2300"}
    assert rows[1].payload["name"] == "Две\nстроки"
    assert rows[1].payload["price"] == " 2.00 "
    assert rows[1].position == {"line_start": 3, "line_end": 4}


def test_xlsx_first_sheet_and_formula_preserved_without_execution():
    rows = list(parse_records(DATA / "valid.xlsx", "XLSX", "FILE", 512_000_000))
    assert rows[0].payload["id"] == "001"
    assert rows[0].payload["price"] == "001.2300"
    assert rows[1].payload["name"] == "=1+1"
    assert rows[1].position["cell_types"][1] == "f"
    assert rows[1].payload["price"] == 2


@pytest.mark.parametrize(
    "field", ['"' + "x" * 1_000_001 + '\n3,phantom\ntail"', '"open\n3,phantom']
)
def test_csv_lost_record_boundary_stops_without_inventing_records(tmp_path, field):
    path = tmp_path / "broken.csv"
    path.write_text("id,name\n1,Before\n2," + field + "\n4,After\n")
    rows = []
    with pytest.raises(ParseFailure) as error:
        rows.extend(parse_records(path, "CSV", "FILE", 512_000_000))
    assert error.value.code == "INVALID_CSV_STRUCTURE"
    assert error.value.position["line_start"] == 3
    assert [row.record_key for row in rows] == ["1"]


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            timedelta(hours=25, minutes=30, milliseconds=123),
            {"excel_type": "timedelta", "days": 1, "seconds": 5400, "microseconds": 123000},
        ),
        (
            timedelta(hours=-1),
            {"excel_type": "timedelta", "days": -1, "seconds": 82800, "microseconds": 0},
        ),
        (
            ArrayFormula(ref="B3", text="=SUM(1,2)"),
            {
                "excel_type": "ArrayFormula",
                "text": "=SUM(1,2)",
                "attributes": {"t": "array", "ref": "B3"},
            },
        ),
        (
            DataTableFormula(ref="B3", r1="B2"),
            {
                "excel_type": "DataTableFormula",
                "attributes": {"t": "dataTable", "ref": "B3", "r1": "B2"},
            },
        ),
    ],
)
def test_xlsx_duration_and_special_formula_values_remain_json_serializable(
    tmp_path, value, expected
):
    path = tmp_path / "typed.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "value"])
    sheet.append(["001", "Before"])
    sheet.append(["002", value])
    sheet.append(["003", "After"])
    workbook.save(path)
    rows = list(parse_records(path, "XLSX", "FILE", 512_000_000))
    assert len(rows) == 3 and not any(row.error_code for row in rows)
    assert rows[1].payload["value"] == expected
    assert rows[1].position["row"] == 3
    assert json.loads(json.dumps(rows[1].payload))["value"] == expected
    assert rows[2].payload == {"id": "003", "value": "After"}


@pytest.mark.parametrize(
    "filename",
    [None, "../a.csv", "a/b.csv", "a\\b.csv", "C:a.csv", "a\x00.csv", "a\n.csv", "x" * 256],
)
def test_filename_path_traversal_is_rejected(filename):
    with pytest.raises(ApiError) as error:
        checked_filename(filename)
    assert error.value.status == 422


def test_storage_hashes_actual_bytes_and_never_overwrites(tmp_path):
    storage = LocalStorage(tmp_path)
    batch_id = uuid4()
    original = (DATA / "valid.csv").read_bytes()
    uri, checksum = storage.save(batch_id, io.BytesIO(original), 100_000_000)
    assert storage.path(uri).read_bytes() == original
    assert checksum == hashlib.sha256(original).hexdigest() == file_checksum(storage.path(uri))
    with pytest.raises(FileExistsError):
        storage.save(batch_id, io.BytesIO(b"replacement"), 100_000_000)
    assert storage.path(uri).read_bytes() == original
    assert not (storage.path(uri).stat().st_mode & 0o222)
    with pytest.raises(ValueError):
        storage.path("local:../../other")


@pytest.mark.parametrize("content", [b"", b"x" * 1025])
def test_empty_and_oversized_storage_are_removed(tmp_path, content):
    with pytest.raises(ApiError):
        LocalStorage(tmp_path).save(uuid4(), io.BytesIO(content), 1024)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("source", list(ImportStatus))
@pytest.mark.parametrize("target", list(ImportStatus))
def test_exact_import_state_machine(source, target):
    batch = ImportBatch(id=uuid4(), source_system_id=uuid4(), status=source)
    if target in TRANSITIONS.get(source, set()):
        from unittest.mock import Mock

        session = Mock()
        transition(session, batch, target)
        assert batch.status == target
        assert session.add.call_count == 1
    else:
        with pytest.raises(ValueError, match="Forbidden"):
            transition(None, batch, target)
        assert batch.status == source


@pytest.mark.parametrize(
    "before,after",
    [
        ('r="3"', 'r="2000000000"'),
        ('r="3"', 'r="1048576"'),
        ('r="C3"', 'r="XFD3"'),
        ('r="C3"', 'r="A3"'),
    ],
)
def test_xlsx_sparse_row_or_column_bombs_rejected(tmp_path, before, after):
    from zipfile import ZipFile

    path = tmp_path / "unsafe.xlsx"
    with ZipFile(DATA / "valid.xlsx") as original, ZipFile(path, "w") as target:
        for info in original.infolist():
            content = original.read(info)
            if info.filename == "xl/worksheets/sheet1.xml":
                assert before.encode() in content
                content = content.replace(before.encode(), after.encode())
            target.writestr(info.filename, content)
    with pytest.raises(ParseFailure) as error:
        check_xlsx(path, 512_000_000)
    assert error.value.code == "UNSAFE_XLSX"


@pytest.mark.parametrize("forged_type", [False, True])
def test_xlsx_relationship_alias_cannot_bypass_row_bounds(tmp_path, forged_type):
    from zipfile import ZipFile

    path = tmp_path / "alias.xlsx"
    old = "xl/worksheets/sheet1.xml"
    alias = "xl/evil/sheet1.bin"
    with ZipFile(DATA / "valid.xlsx") as original, ZipFile(path, "w") as target:
        for info in original.infolist():
            content = original.read(info)
            name = info.filename
            if name == old:
                name = alias
                content = content.replace(b'r="3"', b'r="2000000000"')
            elif name in {"[Content_Types].xml", "xl/_rels/workbook.xml.rels"}:
                content = content.replace(old.encode(), alias.encode())
                if forged_type and name.endswith(".rels"):
                    content = content.replace(b"relationships/worksheet", b"relationships/image", 1)
            target.writestr(name, content)
    with pytest.raises(ParseFailure) as error:
        check_xlsx(path, 512_000_000)
    assert error.value.code == "UNSAFE_XLSX"
