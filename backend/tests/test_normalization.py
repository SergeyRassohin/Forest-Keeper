import json
import random
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.imports.models import RawRecord
from app.normalization.normalize import MISSING, bounded_decimal, decimal_text, extract, normalize
from app.normalization.pipeline import build_record
from app.normalization.profiles import FieldRule, Profile, catalog

EXPECTED = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/data/normalization/expected.json").read_text()
)
PROFILE = next(profile for profile in catalog().values() if profile.code == "synthetic-material")
FIELDS = {field.attribute_code: field for field in PROFILE.bindings[0].fields}


@pytest.mark.parametrize("raw,value,unit,quality", EXPECTED["mass"])
def test_reference_mass(raw, value, unit, quality):
    result = normalize(raw, FIELDS["mass"])
    assert (result.value, result.unit, result.quality) == (value, unit, quality)


@pytest.mark.parametrize("raw,value", EXPECTED["name"])
def test_reference_strings(raw, value):
    result = normalize(raw, FIELDS["name"])
    assert result.value == value and result.quality == "VALID"


@pytest.mark.parametrize("raw,value,quality", EXPECTED["dates"])
def test_reference_dates(raw, value, quality):
    result = normalize(raw, FIELDS["manufactured_on"])
    assert (result.value, result.quality) == (value, quality)


@pytest.mark.parametrize("raw,value,quality", EXPECTED["price"])
def test_reference_decimal(raw, value, quality):
    result = normalize(raw, FIELDS["price"])
    assert (result.value, result.quality) == (value, quality)


@pytest.mark.parametrize(
    "raw,value",
    [
        ("-12,5", "-12.5"),
        ("0", "0"),
        ("-0.000", "0"),
        ("0.000000000000000001", "0.000000000000000001"),
        ("999999999999999999.999999999999999999", "999999999999999999.999999999999999999"),
        ("1e18", "1000000000000000000"),
        (12, "12"),
    ],
)
def test_decimal_precision_and_ranges(raw, value):
    result = normalize(raw, FIELDS["price"])
    assert result.quality == "VALID" and result.value == value


@pytest.mark.parametrize(
    "raw",
    [
        "NaN",
        "inf",
        "1e999",
        "1e-999",
        "1" * 10000,
        "=1+2",
        "0.0000000000000000001",
        "１２.５",
        True,
    ],
)
def test_pathological_or_unsupported_numbers_not_valid(raw):
    result = normalize(raw, FIELDS["price"])
    assert result.quality != "VALID" and result.value is None


def test_float_source_is_not_hidden_as_exact_decimal():
    result = normalize(0.1, FIELDS["price"])
    assert result.value == "0.1" and result.quality == "WARNING"
    assert result.code == "DECODED_FLOAT"


def test_date_policy_does_not_drop_timezone_or_time():
    rule = FIELDS["manufactured_on"]
    assert (
        normalize({"excel_type": "datetime", "iso8601": "2026-10-20T00:00:00"}, rule).quality
        == "WARNING"
    )
    for source in ["2026-10-20T12:30:00", "2026-10-20T00:00:00+03:00"]:
        result = normalize({"excel_type": "datetime", "iso8601": source}, rule)
        assert result.quality == "UNKNOWN" and result.value is None
    ambiguous = rule.model_copy(update={"date_formats": ["%m/%d/%Y", "%d/%m/%Y"]})
    assert normalize("01/02/2003", ambiguous).quality == "UNKNOWN"
    assert normalize("31/02/2023", ambiguous).quality == "INVALID"


def test_missing_null_and_empty_do_not_collapse():
    from uuid import uuid4

    optional = FIELDS["name"]
    assert normalize("", optional).value == ""
    assert normalize(None, optional).value is None
    assert normalize(MISSING, optional).quality == "UNKNOWN"
    assert normalize(MISSING, FIELDS["code"]).quality == "INVALID"
    raw = RawRecord(
        id=uuid4(), raw_payload={"name": "", "price": None}, source_object_type="record"
    )
    entity, values, details = build_record(raw, "CSV", "FILE", PROFILE, PROFILE.digest())
    by_attribute = {value["attribute_code"]: value for value in values}
    assert by_attribute["code"]["normalization_rule"]["presence"] == "missing"
    assert by_attribute["name"]["normalization_rule"]["presence"] == "empty"
    assert by_attribute["price"]["normalization_rule"]["presence"] == "null"


def test_literal_paths_and_duplicate_xml_candidates():
    path = ["children", {"tag": "mass"}, "text"]
    payload = {"children": [{"tag": "mass", "text": "1 кг"}, {"tag": "mass", "text": "2 кг"}]}
    result = normalize(extract(payload, path), FIELDS["mass"])
    assert result.quality == "UNKNOWN"
    assert len(extract(payload, path)) == 2
    with pytest.raises(ValidationError):
        FieldRule(attribute_code="mass", path=[{"eval": "__import__('os')"}], kind="decimal")


def test_profile_snapshot_and_version_fingerprint():
    assert Profile.model_validate(PROFILE.snapshot()).digest() == PROFILE.digest()
    changed = PROFILE.model_copy(update={"version": "2"})
    assert changed.digest() != PROFILE.digest()
    invalid = PROFILE.snapshot()
    invalid["bindings"].append(invalid["bindings"][0])
    with pytest.raises(ValidationError):
        Profile.model_validate(invalid)


def test_seeded_unicode_fuzz_and_string_idempotence():
    rng = random.Random(31214)
    for _ in range(400):
        text = "".join(chr(rng.randrange(0x110000)) for _ in range(rng.randrange(0, 256)))
        for case in ["keep", "upper", "lower", "casefold"]:
            rule = FIELDS["name"].model_copy(update={"case": case})
            result = normalize(text, rule)
            assert normalize(result.value, rule).value == result.value
        for rule in [FIELDS["mass"], FIELDS["price"], FIELDS["manufactured_on"]]:
            assert normalize(text, rule).quality in {"UNKNOWN", "INVALID"}


def test_seeded_exact_unit_equivalence_and_decimal_roundtrip():
    rng = random.Random(31215)
    with localcontext() as context:
        context.prec = 80
        for _ in range(500):
            kilograms = Decimal(rng.randrange(-(10**9), 10**9)) / Decimal(1000)
            canonical = decimal_text(kilograms)
            assert bounded_decimal(canonical) == kilograms
            kg = normalize(canonical + " кг", FIELDS["mass"])
            grams = normalize(decimal_text(kilograms * 1000) + " г", FIELDS["mass"])
            assert kg.value == grams.value == canonical
            assert kg.quality == grams.quality == "VALID"


@pytest.mark.parametrize("source", ["NEW", "QUEUED", "PROCESSING", "COMPLETED", "FAILED"])
@pytest.mark.parametrize("target", ["NEW", "QUEUED", "PROCESSING", "COMPLETED", "FAILED"])
def test_exact_analysis_lifecycle(source, target):
    from unittest.mock import Mock
    from uuid import uuid4

    from app.normalization.jobs import TRANSITIONS, transition
    from app.normalization.models import AnalysisRun, AnalysisStatus

    run = AnalysisRun(
        id=uuid4(),
        status=source,
        mapping_snapshot=PROFILE.snapshot(),
        mapping_hash=PROFILE.digest(),
        actor_id=uuid4(),
        import_batch_ids=[],
    )
    if AnalysisStatus(target) in TRANSITIONS.get(AnalysisStatus(source), set()):
        session = Mock()
        transition(session, run, AnalysisStatus(target))
        assert run.status == target
        session.add.assert_called_once()
    else:
        with pytest.raises(ValueError, match="Forbidden analysis transition"):
            transition(Mock(), run, AnalysisStatus(target))
        assert run.status == source


@pytest.mark.parametrize(
    "trim,collapse,expected",
    [
        (True, True, "A B"),
        (False, True, " A B "),
        (False, False, "  A   B  "),
        (True, False, "A   B"),
    ],
)
def test_trim_and_whitespace_operations_are_independent(trim, collapse, expected):
    rule = FIELDS["name"].model_copy(
        update={"trim": trim, "collapse_whitespace": collapse, "case": "keep"}
    )
    result = normalize("  A   B  ", rule)
    assert result.value == expected
    assert normalize(result.value, rule).value == expected
