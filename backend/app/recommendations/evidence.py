"""Explicit source correspondence and conservative frozen provenance validation."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.conflicts.engine import CONFIG_HASH
from app.decisions.models import Decision
from app.decisions.validation import selectable
from app.imports.models import ImportBatch, RawRecord
from app.matching.models import MatchCandidate, MatchingPair, MatchingRun
from app.matching.profiles import catalog as matching_catalog
from app.normalization.models import AnalysisRecord, AnalysisRun, EntityValue
from app.normalization.profiles import catalog as normalization_catalog
from app.recommendations.policy import Candidate
from app.recommendations.schemas import SourceMap
from app.similarity.context import context, fingerprint
from app.similarity.provider import ProviderError


class EvidenceError(Exception):
    """Only fixed public reason codes, never source payload or internal errors."""


@dataclass
class Prepared:
    candidate: Candidate
    roles: dict[str, str]
    features: dict[str, Any]


def fresh(snapshot: dict[str, Any]) -> bool:
    try:
        matching = snapshot["matching"]
        profiles = {str(key): value for key, value in matching_catalog().items()}
        profile = profiles.get(matching["profile_id"])
        normalization = {str(key): value for key, value in normalization_catalog().items()}
        origins = snapshot["normalization_origins"]
        sides = snapshot["conflict"]["values_snapshot"]
        return bool(
            len(origins) == 2
            and len({x["analysis_id"] for x in origins}) == 2
            and {x["source_id"] for x in origins} == {x["source_id"] for x in sides}
            and profile
            and profile.digest() == matching["profile_hash"]
            and snapshot["conflict"]["basis"]["config_hash"] == CONFIG_HASH
            and all(
                (item := normalization.get(origin["profile_id"])) is not None
                and item.digest() == origin["mapping_hash"]
                for origin in snapshot["normalization_origins"]
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


def prepare(snapshot: dict[str, Any], mapping: SourceMap, row: Decision | None = None) -> Prepared:
    try:
        features = context(snapshot, row)
        if not fresh(snapshot):
            raise EvidenceError("STALE_CONTEXT")
        if features["authority"] != "NOT_DEFINED" or features["forest_codex"].get("configured"):
            # No accepted active authority/Rule adapter yet, never invent precedence.
            raise EvidenceError("AUTHORITY_UNVERIFIABLE")
        if any(
            getattr(mapping, key) != features[key]
            for key in ("domain", "entity_type", "attribute_code")
        ):
            raise EvidenceError("SOURCE_MAPPING_NOT_CONFIGURED")
        if snapshot["matching"]["profile_hash"] not in mapping.matching_profile_hashes:
            raise EvidenceError("SOURCE_MAPPING_AMBIGUOUS")
        source_info = {s["source_id"]: s for s in snapshot["retrieval_sources"]}
        bindings = {str(s.source_id): s for s in mapping.sources}
        sides = snapshot["conflict"]["values_snapshot"]
        roles: dict[str, str] = {}
        correlation = {"semantic:" + fingerprint(features)}
        for side in sides:
            identifier = side["source_id"]
            binding = bindings.get(identifier)
            info = source_info.get(identifier)
            if binding is None or info is None or binding.source_type != info["source_type"]:
                raise EvidenceError("SOURCE_MAPPING_AMBIGUOUS")
            if binding.role in roles.values() or identifier in roles:
                raise EvidenceError("SOURCE_MAPPING_AMBIGUOUS")
            roles[identifier] = binding.role
            file_hash, key, raw_id = (
                side["file_hash"],
                side["source_record_key"],
                side["raw_record_id"],
            )
            if (
                not isinstance(file_hash, str)
                or len(file_hash) != 64
                or any(c not in "0123456789abcdef" for c in file_hash)
                or not isinstance(key, str)
                or not key.strip()
                or len(key) > 256
            ):
                raise EvidenceError("INCOMPLETE_PROVENANCE")
            # UUID/type checks also cover legacy/malformed provenance, without trusting new IDs.
            from uuid import UUID

            UUID(raw_id)
            correlation.update(
                {
                    "file:" + file_hash,
                    "raw:" + raw_id,
                    "key:" + fingerprint([features["domain"], features["entity_type"], key]),
                }
            )
        if len(roles) != 2 or features["synthetic"] is not True:
            raise EvidenceError("SOURCE_MAPPING_AMBIGUOUS")
        selected_role = None
        if row is not None and row.decision_type == "SELECT_VALUE":
            selected = [
                s
                for s in sides
                if s["source_id"] == str(row.selected_source_id)
                and s.get("value")
                and s["value"]["value_id"] == str(row.selected_value_id)
            ]
            if (
                len(selected) != 1
                or not selectable(selected[0])
                or selected[0]["value"]["normalized_value"] != row.selected_value
                or selected[0]["value"]["kind"] != row.value_kind
                or selected[0]["value"].get("unit") != row.unit
            ):
                raise EvidenceError("CORRUPT_LINEAGE")
            selected_role = roles[str(row.selected_source_id)]
        return Prepared(
            Candidate(
                str(row.id) if row else "CURRENT",
                frozenset(correlation),
                row.decision_type if row else "CURRENT",
                selected_role,
            ),
            roles,
            features,
        )
    except EvidenceError:
        raise
    except (KeyError, TypeError, ValueError, ProviderError):
        raise EvidenceError("CORRUPT_LINEAGE") from None


def validate_lineage(session: Session, snapshots: list[dict[str, Any]]) -> None:
    """Bounded provenance projections, never load RawRecord payloads or infer roles."""
    from uuid import UUID

    try:
        sides = [side for snapshot in snapshots for side in snapshot["conflict"]["values_snapshot"]]
        raw_ids = {UUID(side["raw_record_id"]) for side in sides}
        raw = {
            str(row.id): row
            for row in session.execute(
                select(
                    RawRecord.id,
                    RawRecord.import_batch_id,
                    RawRecord.source_record_key,
                    ImportBatch.source_system_id,
                    ImportBatch.file_hash,
                )
                .join(ImportBatch, ImportBatch.id == RawRecord.import_batch_id)
                .where(RawRecord.id.in_(raw_ids))
            )
        }
        value_ids = {UUID(side["value"]["value_id"]) for side in sides if side.get("value")}
        values = {
            str(row.id): row
            for row in session.execute(
                select(
                    EntityValue.id,
                    EntityValue.raw_record_id,
                    EntityValue.entity_id,
                    EntityValue.normalized_value,
                    EntityValue.unit,
                    EntityValue.quality_status,
                    EntityValue.normalization_rule,
                ).where(EntityValue.id.in_(value_ids))
            )
        }
        expected = []
        for snapshot in snapshots:
            origins = {x["source_id"]: x for x in snapshot["normalization_origins"]}
            for side in snapshot["conflict"]["values_snapshot"]:
                expected.append((side, origins[side["source_id"]]))
        pairs = {
            (UUID(origin["analysis_id"]), UUID(side["raw_record_id"])) for side, origin in expected
        }
        normalized = {
            (str(row.analysis_id), str(row.raw_record_id)): row
            for row in session.execute(
                select(
                    AnalysisRecord.analysis_id,
                    AnalysisRecord.raw_record_id,
                    AnalysisRecord.entity_id,
                    AnalysisRun.template_id,
                    AnalysisRun.mapping_hash,
                    AnalysisRun.mapping_snapshot,
                    AnalysisRun.status,
                )
                .join(AnalysisRun, AnalysisRun.id == AnalysisRecord.analysis_id)
                .where(tuple_(AnalysisRecord.analysis_id, AnalysisRecord.raw_record_id).in_(pairs))
            )
        }
        for side, origin in expected:
            run = normalized.get((origin["analysis_id"], side["raw_record_id"]))
            if (
                run is None
                or run.status != "COMPLETED"
                or str(run.entity_id) != side["entity_id"]
                or str(run.template_id) != origin["profile_id"]
                or run.mapping_hash != origin["mapping_hash"]
                or run.mapping_snapshot["engine_version"] != origin["engine_version"]
                or run.mapping_snapshot["version"] != origin["profile_version"]
            ):
                raise EvidenceError("CORRUPT_LINEAGE")
        match_ids = {
            (UUID(s["conflict"]["matching_run_id"]), UUID(s["conflict"]["match_candidate_id"]))
            for s in snapshots
        }
        matched = {
            (str(row.run_id), str(row.candidate_id)): row
            for row in session.execute(
                select(
                    MatchingPair.run_id,
                    MatchingPair.candidate_id,
                    MatchCandidate.raw_record_a_id,
                    MatchCandidate.raw_record_b_id,
                    MatchCandidate.status.label("candidate_status"),
                    MatchCandidate.evidence,
                    MatchingRun.status.label("run_status"),
                    MatchingRun.profile_id,
                    MatchingRun.profile_hash,
                    MatchingRun.profile_snapshot,
                    MatchingRun.input_context,
                )
                .join(MatchCandidate, MatchCandidate.id == MatchingPair.candidate_id)
                .join(MatchingRun, MatchingRun.id == MatchingPair.run_id)
                .where(tuple_(MatchingPair.run_id, MatchingPair.candidate_id).in_(match_ids))
            )
        }
        for snapshot in snapshots:
            case = snapshot["conflict"]
            run = matched.get((case["matching_run_id"], case["match_candidate_id"]))
            frozen_match = snapshot["matching"]
            if (
                run is None
                or run.run_status != "COMPLETED"
                or run.candidate_status != "MATCHED"
                or {str(run.raw_record_a_id), str(run.raw_record_b_id)}
                != {side["raw_record_id"] for side in case["values_snapshot"]}
                or frozen_match["run_id"] != str(run.run_id)
                or frozen_match["profile_id"] != str(run.profile_id)
                or frozen_match["profile_hash"] != run.profile_hash
                or frozen_match["profile_snapshot"] != run.profile_snapshot
                or frozen_match["input_context"] != run.input_context
                or case["basis"]["matching_evidence"] != run.evidence
            ):
                raise EvidenceError("CORRUPT_LINEAGE")
        for side in sides:
            source = raw.get(side["raw_record_id"])
            if (
                source is None
                or str(source.source_system_id) != side["source_id"]
                or source.file_hash != side["file_hash"]
                or str(source.import_batch_id) != side["import_batch_id"]
                or source.source_record_key != side["source_record_key"]
            ):
                raise EvidenceError("CORRUPT_LINEAGE")
            if side.get("value"):
                frozen = side["value"]
                actual = values.get(frozen["value_id"])
                if (
                    actual is None
                    or str(actual.raw_record_id) != side["raw_record_id"]
                    or str(actual.entity_id) != side["entity_id"]
                    or actual.normalized_value != frozen["normalized_value"]
                    or actual.unit != frozen.get("unit")
                    or actual.quality_status != frozen["quality_status"]
                    or actual.normalization_rule != frozen["normalization_rule"]
                ):
                    raise EvidenceError("CORRUPT_LINEAGE")
    except EvidenceError:
        raise
    except (KeyError, TypeError, ValueError):
        raise EvidenceError("CORRUPT_LINEAGE") from None
