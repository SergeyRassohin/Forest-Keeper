from typing import Any
from uuid import UUID, uuid5

from app.imports.models import RawRecord
from app.normalization.normalize import MISSING, extract, normalize
from app.normalization.profiles import Profile

IDENTITY_NAMESPACE = UUID("e62f7223-f060-5169-8b27-f22290811628")


def build_record(
    raw: RawRecord, file_format: str, source_type: str, profile: Profile, digest: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    binding = profile.binding(file_format, source_type, raw.source_object_type)
    if binding is None:
        return None, [], {"code": "UNMAPPED_OBJECT", "unmapped_fields": []}
    entity_id = uuid5(IDENTITY_NAMESPACE, raw.id.hex + ":" + digest)
    values = []
    display_name = raw.source_record_key or str(raw.id)
    for field in binding.fields:
        source = extract(raw.raw_payload, field.path)
        result = normalize(source, field)
        presence = (
            "missing"
            if source is MISSING
            else "null"
            if source is None
            else "empty"
            if source == ""
            else "present"
        )
        evidence: dict[str, Any] = {
            "mapping": digest,
            "field": field.attribute_code,
            "presence": presence,
            "code": result.code,
        }
        if result.conversion:
            evidence["conversion"] = result.conversion
        values.append(
            {
                "id": uuid5(entity_id, field.attribute_code),
                "entity_id": entity_id,
                "attribute_code": field.attribute_code,
                "raw_record_id": raw.id,
                "raw_value": None if source is MISSING else source,
                "normalized_value": result.value,
                "unit": result.unit,
                "quality_status": result.quality,
                "normalization_rule": evidence,
            }
        )
        if field.attribute_code == profile.display_attribute and result.value is not None:
            display_name = result.value
    if file_format == "XML":
        known = {
            segment["tag"]
            for field in binding.fields
            for segment in field.path
            if isinstance(segment, dict)
        }
        unmapped = sorted(
            {node.get("tag", "") for node in raw.raw_payload.get("children", [])} - known
        )
    else:
        known = {field.path[0] for field in binding.fields if isinstance(field.path[0], str)}
        unmapped = sorted(set(raw.raw_payload) - known)
    return (
        {
            "id": entity_id,
            "domain": profile.domain,
            "entity_type": profile.entity_type,
            "display_name": display_name[:200],
            "status": None,
        },
        values,
        {"code": "OK", "unmapped_fields": unmapped},
    )
