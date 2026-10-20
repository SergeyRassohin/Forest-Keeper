import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from app.normalization.profiles import FieldRule

MISSING = object()
NUMBER = r"[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)(?:[eE][+-]?[0-9]{1,3})?"
DATE_PATTERNS = {
    "%Y-%m-%d": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    "%d.%m.%Y": r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}",
    "%d/%m/%Y": r"[0-9]{2}/[0-9]{2}/[0-9]{4}",
    "%m/%d/%Y": r"[0-9]{2}/[0-9]{2}/[0-9]{4}",
}


@dataclass
class Normalized:
    value: str | None
    quality: str
    code: str
    unit: str | None = None
    conversion: dict[str, str] | None = None


def extract(payload: Any, path: list[str | dict[str, str]]) -> Any:
    current = payload
    for segment in path:
        if isinstance(segment, str):
            if not isinstance(current, dict) or segment not in current:
                return MISSING
            current = current[segment]
        else:
            if not isinstance(current, list):
                return MISSING
            matches = [
                item
                for item in current
                if isinstance(item, dict) and item.get("tag") == segment["tag"]
            ]
            if not matches:
                return MISSING
            if len(matches) > 1:
                return matches  # Preserve both candidates; unsupported type -> UNKNOWN.
            current = matches[0]
    return current


def decimal_text(value: Decimal) -> str:
    if not value:
        return "0"
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def bounded_decimal(text: str) -> Decimal | None:
    if len(text) > 128 or not re.fullmatch(NUMBER, text):
        return None
    try:
        value = Decimal(text.replace(",", "."))
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or len(value.as_tuple().digits) > 38
            or not isinstance(exponent, int)
            or not -18 <= exponent <= 18
            or (value and not -18 <= value.adjusted() <= 18)
        ):
            return None
        return value
    except InvalidOperation:
        return None


def normalize(raw: Any, rule: FieldRule) -> Normalized:
    if raw is MISSING or raw is None:
        return Normalized(
            None, "INVALID" if rule.required else "UNKNOWN", "MISSING" if raw is MISSING else "NULL"
        )
    if isinstance(raw, str) and len(raw) > 4096:
        return Normalized(None, "INVALID", "INPUT_TOO_LONG")
    if rule.kind == "string":
        if not isinstance(raw, str):
            return Normalized(None, "UNKNOWN", "UNSUPPORTED_TYPE")
        value = unicodedata.normalize("NFC", raw)
        if rule.trim:
            value = value.strip()
        if rule.collapse_whitespace:
            value = re.sub(r"\s+", " ", value)
        if rule.case != "keep":
            value = getattr(value, rule.case)()
        value = unicodedata.normalize("NFC", value)
        return Normalized(
            value,
            "INVALID" if rule.required and not value else "VALID",
            "EMPTY_REQUIRED" if rule.required and not value else "OK",
        )
    if rule.kind == "date":
        return normalize_date(raw, rule)
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        return Normalized(None, "UNKNOWN", "UNSUPPORTED_TYPE")
    if isinstance(raw, int) and raw.bit_length() > 128:
        return Normalized(None, "INVALID", "NUMBER_RANGE")
    text = str(raw).strip()
    if "," in text and "." in text:
        return Normalized(None, "UNKNOWN", "AMBIGUOUS_SEPARATOR")
    unit = None
    factor = Decimal(1)
    evidence = None
    if rule.kind == "quantity":
        match = re.fullmatch(r"(" + NUMBER + r")\s*([^0-9\s.,+\-]+)?", text)
        if match is None:
            return Normalized(None, "INVALID", "INVALID_NUMBER")
        alias = (match[2] or "").casefold()
        if alias not in rule.unit_aliases:
            return Normalized(None, "UNKNOWN", "UNKNOWN_UNIT")
        text = match[1]
        factor = Decimal(rule.unit_aliases[alias])
        unit = rule.unit
        evidence = {"source_unit": match[2], "factor": str(factor)}
    number = bounded_decimal(text)
    if number is None:
        return Normalized(None, "INVALID", "INVALID_NUMBER")
    with localcontext() as context:
        context.prec = 80
        number *= factor
        if bounded_decimal(decimal_text(number)) is None:
            return Normalized(None, "INVALID", "NUMBER_RANGE")
        return Normalized(
            decimal_text(number),
            "WARNING" if isinstance(raw, float) else "VALID",
            "DECODED_FLOAT" if isinstance(raw, float) else "OK",
            unit,
            evidence,
        )


def normalize_date(raw: Any, rule: FieldRule) -> Normalized:
    code = "OK"
    if isinstance(raw, dict) and raw.get("excel_type") in {"date", "datetime"}:
        if raw["excel_type"] == "datetime":
            value = raw.get("iso8601", "")
            if (
                not rule.allow_midnight_datetime
                or not isinstance(value, str)
                or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T00:00:00", value)
            ):
                return Normalized(None, "UNKNOWN", "DATETIME_POLICY")
            raw, code = value[:10], "DATE_FROM_MIDNIGHT"
        else:
            raw = raw.get("iso8601")
    if not isinstance(raw, str):
        return Normalized(None, "UNKNOWN", "UNSUPPORTED_TYPE")
    text = raw.strip()
    candidates = set()
    matched = False
    for fmt in rule.date_formats:
        if re.fullmatch(DATE_PATTERNS[fmt], text):
            matched = True
            try:
                candidates.add(datetime.strptime(text, fmt).date().isoformat())
            except ValueError:
                continue
    if len(candidates) == 1:
        return Normalized(candidates.pop(), "VALID" if code == "OK" else "WARNING", code)
    if len(candidates) > 1 or (not matched and "/" in text):
        return Normalized(None, "UNKNOWN", "AMBIGUOUS_DATE")
    return Normalized(
        None, "INVALID" if matched else "UNKNOWN", "INVALID_DATE" if matched else "DATE_FORMAT"
    )
