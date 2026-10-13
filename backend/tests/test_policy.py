import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from app.auth.models import Role, User, UserRole
from app.auth.policy import PERMISSIONS, permissions_for, permits


def canonical_matrix() -> dict[str, set[Role]]:
    source = Path(__file__).resolve().parents[2] / "docs/security/access-control-matrix-v0.1.xlsx"
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(source) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(item.itertext())
                for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", ns)
            ]

        def value(cell: ET.Element) -> str:
            raw = cell.find("s:v", ns)
            inline = cell.find("s:is", ns)
            if cell.get("t") == "s":
                assert raw is not None and raw.text is not None
                return strings[int(raw.text)]
            return (
                "".join(inline.itertext())
                if inline is not None
                else raw.text or ""
                if raw is not None
                else ""
            )

        rows = ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//s:row", ns)
        headers = {cell.attrib["r"][0]: value(cell) for cell in rows[0].findall("s:c", ns)}
        role_columns = {column: Role(headers[column]) for column in "DEFG"}
        matrix = {}
        for row in rows[1:]:
            cells = {cell.attrib["r"][0]: value(cell) for cell in row.findall("s:c", ns)}
            matrix[cells["C"]] = {
                role for column, role in role_columns.items() if cells[column] == "✓"
            }
        return matrix


def test_permission_catalog_matches_authoritative_workbook() -> None:
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads((root / "backend/app/auth/permissions.json").read_text())
    assert catalog["sha256"] == hashlib.sha256((root / catalog["source"]).read_bytes()).hexdigest()
    assert PERMISSIONS == canonical_matrix()
    assert len(PERMISSIONS) == 39


def test_admin_has_no_implicit_business_role_and_union_is_explicit() -> None:
    user = User(roles=[UserRole(role_code="ADMIN")])
    assert permits(user, "user.manage")
    assert not permits(user, "decision.create")
    assert not permits(user, "match.review")
    assert not permits(user, "rule.activate")
    user.roles.append(UserRole(role_code="REVIEWER"))
    assert permits(user, "decision.create")
    assert not permits(user, "rule.activate")
    assert not permits(user, "invented.permission")
    user.roles = []
    assert permissions_for(user) == []
