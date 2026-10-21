import json
from collections import Counter, defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.conflicts.engine import CONFIG, basis, compare, conflict_id
from app.conflicts.models import Conflict, ConflictInput, ConflictOutput, ConflictRun
from app.imports.models import ImportBatch, RawRecord, SourceSystem
from app.matching.models import MatchCandidate, MatchingRun
from app.normalization.models import AnalysisRun, EntityValue
from app.normalization.profiles import Profile


def load_values(
    session: Session, entities: list[UUID], runs: list[AnalysisRun]
) -> dict[str, dict[str, Any]]:
    profiles = {run.mapping_hash: Profile.model_validate(run.mapping_snapshot) for run in runs}
    result: dict[str, dict[str, Any]] = defaultdict(dict)
    for value, file_format, source_type, object_type in session.execute(
        select(
            EntityValue, ImportBatch.format, SourceSystem.source_type, RawRecord.source_object_type
        )
        .join(RawRecord, RawRecord.id == EntityValue.raw_record_id)
        .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
        .join(SourceSystem, SourceSystem.id == ImportBatch.source_system_id)
        .where(EntityValue.entity_id.in_(entities))
    ):
        profile = profiles[value.normalization_rule["mapping"]]
        binding = profile.binding(file_format, source_type, object_type)
        if binding is None:
            raise ValueError("Missing normalization binding")
        field = next(
            field for field in binding.fields if field.attribute_code == value.attribute_code
        )
        bounded_raw = isinstance(value.raw_value, (str, int, float, bool, type(None))) and (
            not isinstance(value.raw_value, str) or len(value.raw_value) <= 4096
        )
        result[str(value.entity_id)][value.attribute_code] = {
            "value_id": str(value.id),
            "raw_value": value.raw_value if bounded_raw else None,
            "raw_value_omitted": not bounded_raw,
            "normalized_value": value.normalized_value,
            "unit": value.unit,
            "quality_status": value.quality_status,
            "normalization_rule": value.normalization_rule,
            "kind": field.kind,
        }
    return result


def process_chunk(session: Session, run: ConflictRun) -> bool:
    matching = session.get(MatchingRun, run.matching_run_id)
    if matching is None or matching.status != "COMPLETED":
        raise ValueError("Matching not completed")
    query = (
        select(MatchCandidate)
        .join(ConflictInput, ConflictInput.candidate_id == MatchCandidate.id)
        .where(ConflictInput.run_id == run.id, MatchCandidate.status == "MATCHED")
    )
    if run.last_candidate_id:
        query = query.where(MatchCandidate.id > run.last_candidate_id)
    candidates = session.scalars(query.order_by(MatchCandidate.id).limit(100)).all()
    if not candidates:
        return False
    origins = [
        session.get(AnalysisRun, UUID(identifier)) for identifier in matching.input_analysis_ids
    ]
    if any(value is None or value.status != "COMPLETED" for value in origins):
        raise ValueError("Missing normalization origin")
    runs = [value for value in origins if value is not None]
    entities = [
        UUID(item["entity_id"]) for candidate in candidates for item in candidate.evidence["inputs"]
    ]
    values = load_values(session, entities, runs)
    raw_ids = [
        UUID(item["raw_record_id"])
        for candidate in candidates
        for item in candidate.evidence["inputs"]
    ]
    provenance = {}
    for raw, batch, source in session.execute(
        select(RawRecord, ImportBatch, SourceSystem)
        .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
        .join(SourceSystem, SourceSystem.id == ImportBatch.source_system_id)
        .where(RawRecord.id.in_(raw_ids))
    ):
        provenance[str(raw.id)] = {
            "raw_record_id": str(raw.id),
            "source_id": str(source.id),
            "source_name": source.name,
            "import_batch_id": str(batch.id),
            "filename": batch.original_filename,
            "file_hash": batch.file_hash,
            "source_record_key": raw.source_record_key,
            "source_position": raw.source_position,
        }
    peers: dict[UUID, set[UUID]] = defaultdict(set)
    for a, b in session.execute(
        select(MatchCandidate.raw_record_a_id, MatchCandidate.raw_record_b_id)
        .join(ConflictInput, ConflictInput.candidate_id == MatchCandidate.id)
        .where(
            ConflictInput.run_id == run.id,
            or_(
                MatchCandidate.raw_record_a_id.in_(raw_ids),
                MatchCandidate.raw_record_b_id.in_(raw_ids),
            ),
        )
    ):
        peers[a].add(b)
        peers[b].add(a)
    reviews = {
        str(event.object_id): {
            "audit_event_id": str(event.id),
            "actor_id": str(event.user_id),
            "reason": event.payload["reason"],
            "reviewed_at": event.created_at.isoformat(),
        }
        for event in session.scalars(
            select(AuditEvent).where(
                AuditEvent.object_id.in_([candidate.id for candidate in candidates]),
                AuditEvent.event_type == "MATCH_REVIEWED",
            )
        )
    }
    counts = Counter(run.status_counts)
    for candidate in candidates:
        inputs = candidate.evidence["inputs"]
        left, right = [values[item["entity_id"]] for item in inputs]
        for attribute in sorted(left.keys() | right.keys()):
            run.attributes_evaluated += 1
            duplicate_peers = {
                str(raw): [str(peer) for peer in sorted(peers[raw])]
                for raw in [candidate.raw_record_a_id, candidate.raw_record_b_id]
                if len(peers[raw]) > 1
            }
            compared = compare(left.get(attribute), right.get(attribute))
            if attribute == matching.profile_snapshot["identifier_attribute"] and duplicate_peers:
                compared = ("DUPLICATE", "MULTIPLE_MATCHED_RECORDS_SAME_SOURCE")
            if compared is None:
                continue
            kind, reason = compared
            identifier = conflict_id(
                candidate.id,
                attribute,
                kind,
                json.dumps(duplicate_peers, sort_keys=True) if kind == "DUPLICATE" else "",
            )
            snapshots = [
                {
                    **provenance[item["raw_record_id"]],
                    "entity_id": item["entity_id"],
                    "value": observations.get(attribute),
                    "presence": basis(reason, [observations.get(attribute)])["presence"][0],
                }
                for item, observations in zip(inputs, [left, right], strict=True)
            ]
            evidence = basis(reason, [left.get(attribute), right.get(attribute)])
            evidence["human_match_review"] = reviews.get(str(candidate.id))
            evidence["duplicate_identity_peers"] = duplicate_peers if kind == "DUPLICATE" else {}
            evidence.update(
                matching_profile_hash=matching.profile_hash,
                matching_profile_snapshot=matching.profile_snapshot,
                matching_evidence=candidate.evidence,
                identity_status="MATCHED",
                confirmed_by=str(candidate.confirmed_by) if candidate.confirmed_by else None,
                normalization_context=matching.input_context,
            )
            created = session.execute(
                insert(Conflict)
                .values(
                    id=identifier,
                    entity_id=UUID(inputs[0]["entity_id"]),
                    analysis_run_id=runs[0].id,
                    matching_run_id=matching.id,
                    match_candidate_id=candidate.id,
                    attribute_code=attribute,
                    conflict_type=kind,
                    severity=CONFIG["severity"],
                    status="OPEN",
                    values_snapshot=snapshots,
                    basis=evidence,
                )
                .on_conflict_do_nothing()
                .returning(Conflict.id)
            ).scalar_one_or_none()
            session.execute(
                insert(ConflictOutput)
                .values(run_id=run.id, conflict_id=identifier)
                .on_conflict_do_nothing()
            )
            if created:
                session.add(
                    AuditEvent(
                        event_type="CONFLICT_CREATED",
                        user_id=run.actor_id,
                        object_type="Conflict",
                        object_id=identifier,
                        payload={
                            "run_id": str(run.id),
                            "matching_run_id": str(matching.id),
                            "candidate_id": str(candidate.id),
                            "type": kind,
                            "status": "OPEN",
                            "severity": CONFIG["severity"],
                            "config_hash": evidence["config_hash"],
                        },
                    )
                )
            counts[kind] += 1
            run.conflicts_generated += 1
        run.records_processed += 1
        run.last_candidate_id = candidate.id
    run.status_counts = dict(counts)
    return True
