from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports.models import ImportBatch, RawRecord
from app.matching.engine import Observation, Record
from app.matching.profiles import MatchingProfile
from app.normalization.models import AnalysisRecord, CanonicalEntity, EntityValue


def load_records(
    session: Session, analysis_id: UUID, profile: MatchingProfile
) -> dict[UUID, Record]:
    attributes = [signal.attribute_code for signal in profile.signals]
    query = (
        select(
            RawRecord.id.label("raw_id"),
            CanonicalEntity.id.label("entity_id"),
            ImportBatch.source_system_id,
            EntityValue.attribute_code,
            EntityValue.normalized_value,
            EntityValue.quality_status,
            EntityValue.unit,
            EntityValue.id.label("value_id"),
        )
        .select_from(AnalysisRecord)
        .join(RawRecord, RawRecord.id == AnalysisRecord.raw_record_id)
        .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
        .join(CanonicalEntity, CanonicalEntity.id == AnalysisRecord.entity_id)
        .join(EntityValue, EntityValue.entity_id == CanonicalEntity.id)
        .where(
            AnalysisRecord.analysis_id == analysis_id,
            CanonicalEntity.domain == profile.domain,
            CanonicalEntity.entity_type == profile.entity_type,
            EntityValue.attribute_code.in_(attributes),
        )
        .execution_options(yield_per=1000)
    )
    records: dict[UUID, Record] = {}
    for row in session.execute(query).mappings():
        record = records.setdefault(
            row["raw_id"], Record(row["raw_id"], row["entity_id"], row["source_system_id"], {})
        )
        value = row["normalized_value"]
        record.values[row["attribute_code"]] = Observation(
            value if isinstance(value, str) else None,
            row["quality_status"],
            row["unit"],
            str(row["value_id"]),
        )
    return records
