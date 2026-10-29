"""Approved deployment profiles are reused within one evaluation, then reloaded."""

from dataclasses import replace
from types import MappingProxyType

import pytest

from app.conflicts.engine import CONFIG_HASH
from app.recommendations import evidence


def approved_case():
    matching = next(iter(evidence.matching_catalog().values()))
    normalization = next(iter(evidence.normalization_catalog().values()))
    snapshot = {
        "matching": {"profile_id": str(matching.id), "profile_hash": matching.digest()},
        "normalization_origins": [
            {
                "analysis_id": str(i),
                "source_id": str(i),
                "profile_id": str(normalization.id),
                "mapping_hash": normalization.digest(),
            }
            for i in range(2)
        ],
        "conflict": {
            "values_snapshot": [{"source_id": str(i)} for i in range(2)],
            "basis": {"config_hash": CONFIG_HASH},
        },
    }
    return snapshot


@pytest.mark.parametrize("catalog", ["matching", "normalization"])
def test_one_immutable_profile_snapshot_and_next_evaluation_reload(catalog, monkeypatch):
    snapshot = approved_case()
    captured = evidence.profile_digests()
    assert evidence.fresh(snapshot, profiles=captured) is True
    with pytest.raises(TypeError):
        captured.matching["unexpected"] = "changed"
    original = getattr(evidence, catalog + "_catalog")()
    changed = {
        key: profile.model_copy(update={"version": "changed"}) for key, profile in original.items()
    }
    monkeypatch.setattr(evidence, catalog + "_catalog", lambda: changed)
    assert evidence.fresh(snapshot, profiles=captured) is True
    assert evidence.fresh(snapshot) is False


@pytest.mark.parametrize("catalog", ["matching", "normalization"])
@pytest.mark.parametrize("missing", [None, ""])
def test_missing_digest_never_matches_missing_historical_hash(catalog, missing):
    snapshot = approved_case()
    captured = evidence.profile_digests()
    key = (
        snapshot["matching"]["profile_id"]
        if catalog == "matching"
        else (snapshot["normalization_origins"][0]["profile_id"])
    )
    # Corrupt both the historical claim and the injected internal map: absence
    # must never become approval through None==None or empty-string equality.
    if catalog == "matching":
        snapshot["matching"]["profile_hash"] = missing
    else:
        for origin in snapshot["normalization_origins"]:
            origin["mapping_hash"] = missing
    values = {} if missing is None else {key: missing}
    captured = replace(captured, **{catalog: MappingProxyType(values)})
    assert evidence.fresh(snapshot, profiles=captured) is False


@pytest.mark.parametrize("damage", ["source", "analysis", "config"])
def test_reusing_catalog_preserves_origin_and_configuration_checks(damage):
    snapshot = approved_case()
    captured = evidence.profile_digests()
    if damage == "source":
        snapshot["normalization_origins"][0]["source_id"] = "outside"
    elif damage == "analysis":
        snapshot["normalization_origins"][0]["analysis_id"] = "1"
    else:
        snapshot["conflict"]["basis"]["config_hash"] = "stale"
    assert evidence.fresh(snapshot) is False
    assert evidence.fresh(snapshot, profiles=captured) is False


def test_malformed_catalog_keeps_existing_stale_context_failure(monkeypatch):
    snapshot = approved_case()

    def invalid_catalog():
        raise ValueError("Private invalid profile content")

    monkeypatch.setattr(evidence, "matching_catalog", invalid_catalog)
    assert evidence.fresh(snapshot) is False
    with pytest.raises(evidence.EvidenceError, match="^STALE_CONTEXT$"):
        evidence.profile_digests()
