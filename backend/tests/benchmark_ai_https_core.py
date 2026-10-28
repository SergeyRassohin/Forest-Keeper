"""Real local TLS/core load while actual Qwen backfill runs; no AI/Decision POSTs.

This is a core metadata test, not semantic quality, full-index ranking or LLM timing.
The only authentication is the existing owned fixture's ten browser cookie sessions.
"""

import hashlib
import json
import math
import os
import re
import ssl
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from uuid import UUID, uuid4

import httpx

from app.auth.dependencies import COOKIE_NAME
from tests.benchmark_ai_capacity import retrieval_expectation

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "work/stage9-capacity-private/actual-10k-v1"
BASE = "https://localhost:18457"
SERVER = "fk-stage9-capacity-ai-browser-backend-1"

# Fixed SELECTs only. Values sent on stdin contain only owned IDs/schema, no credentials.
PROBE = """
import json,re,sys
from uuid import UUID
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session
from app.common.config import Settings
from app.common.database import make_engine
from app.decisions.models import Decision
from app.similarity.models import DecisionEmbedding,IndexRun
d=json.load(sys.stdin)
assert re.fullmatch(r"auth_test_[a-f0-9]{32}", d["schema"])
e=make_engine(Settings())
with Session(e) as s:
 assert s.scalar(text("SELECT current_schema()"))==d["schema"]
 tables=("source_systems","import_batches","raw_records","analysis_runs","canonical_entities",
         "entity_values","matching_runs","match_candidates","conflicts","decisions")
 digests={n:s.scalar(text("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' "
            "ORDER BY to_jsonb(t)::text),'')) FROM "+n+" t")) for n in tables}
 run=s.get(IndexRun, UUID(d["run_id"]))
 print(json.dumps({"decisions":s.scalar(select(func.count()).select_from(Decision)),
    "vectors":s.scalar(select(func.count()).select_from(DecisionEmbedding)),
    "index_status":run.status,"business_digests":digests}))
e.dispose()
"""


def probe(value):
    response = subprocess.run(
        ["docker", "exec", "-i", SERVER, "python", "-c", PROBE],
        input=json.dumps({k: value[k] for k in ("schema", "run_id")}),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if response.returncode != 0:
        raise RuntimeError("Owned database probe failed; no raw diagnostic exposed")
    result = json.loads(response.stdout)
    assert result["decisions"] == 10000
    return result


def observe(
    client,
    category,
    path,
    query,
    decision,
    history,
    cases,
    version=None,
    target=None,
    expected_reason="EVIDENCE_WINDOW_EXCEEDED",
):
    since = time.monotonic()
    row = {"endpoint": category, "valid": False, "status_code": None, "error_code": None}
    try:
        response = client.get(path)
        row["status_code"] = response.status_code
        data = response.json()
        valid = response.status_code == 200
        if category == "conflict_list":
            valid = (
                valid
                and isinstance(data, list)
                and len(data) == 50
                and all(isinstance(item, dict) and item.get("id") in cases for item in data)
            )
        elif category == "registry_list":
            valid = (
                valid
                and isinstance(data, list)
                and len(data) == 50
                and all(
                    isinstance(item, dict) and item.get("conflict_id") in history for item in data
                )
            )
        elif category == "decision_detail":
            valid = valid and isinstance(data, dict) and data.get("id") == decision
        elif category == "review_context":
            valid = valid and isinstance(data, dict) and data.get("conflict_id") == query
        elif category == "conflict_detail":
            valid = valid and isinstance(data, dict) and data.get("id") == query
        elif category == "similar_decisions":
            valid = (
                valid
                and version is not None
                and target is not None
                and retrieval_expectation(data, version, target, history) is not None
            )
        elif category == "recommendation":
            valid = (
                valid
                and isinstance(data, dict)
                and (
                    data.get("status") == "ABSTAINED" and data.get("reason_code") == expected_reason
                )
            )
        else:
            valid = False
        row["valid"] = valid
    except Exception as error:
        row["valid"] = False
        row["error_code"] = type(error).__name__[:64]
    row["seconds"] = round(time.monotonic() - since, 6)
    return row


def main():
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Explicit owned development fixture opt-in required")
    value = json.loads((FIXTURE / "fixture.json").read_text())
    assert value["kind"] == "owned-stage9-distinct-file-capacity-v1-not-gold"
    assert value["phase"] in {"INDEXING", "INDEXED"} and value["target"] == 10000
    mode = os.getenv("FK_AI_CORE_MODE", "metadata")
    assert mode in {"metadata", "retrieval"}
    if mode == "retrieval":
        assert value["phase"] == "INDEXED", "Never measure full ranking on a partial index"
    activity = os.getenv(
        "FK_AI_CORE_REQUIRE_ACTIVITY", "embedding" if value["phase"] == "INDEXING" else "none"
    )
    assert activity in {"embedding", "llm", "none"}
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", value["schema"])
    assert len(set(value["tokens"])) == 10
    for identifier in value["queries"]:
        UUID(identifier)
    label = subprocess.check_output(
        [
            "docker",
            "inspect",
            SERVER,
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}',
        ],
        text=True,
    ).strip()
    assert label == "fk-stage9-capacity"
    report = FIXTURE / "evidence" / ("core-https-" + activity + "-" + uuid4().hex + ".json")
    source = Path(__file__).read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    source_artifact = report.parent / ("https-observer-source-" + source_hash + ".py.txt")
    if source_artifact.exists():
        assert source_artifact.read_bytes() == source
    else:
        with source_artifact.open("xb") as out:
            out.write(source)
    contract_source = Path(retrieval_expectation.__code__.co_filename).read_bytes()
    contract_hash = hashlib.sha256(contract_source).hexdigest()
    contract_artifact = report.parent / ("retrieval-contract-source-" + contract_hash + ".py.txt")
    if contract_artifact.exists():
        assert contract_artifact.read_bytes() == contract_source
    else:
        with contract_artifact.open("xb") as out:
            out.write(contract_source)
    result = {
        "kind": "actual-https-core-metadata-load-not-quality",
        "passed": False,
        "sessions": 10,
        "planned_requests": 500,
        "started_at": datetime.now(UTC).isoformat(),
        "transport": "actual local HTTPS/nginx/API/PG/Redis",
        "full_index_ranking_measured": mode == "retrieval",
        "llm_measured": False,
        "production_accepted": False,
        "semantic_quality_evaluated": False,
        "required_overlap_component": activity,
        "observer_source_sha256": source_hash,
        "observer_source_artifact": source_artifact.name,
        "retrieval_contract_source_sha256": contract_hash,
        "retrieval_contract_source_artifact": contract_artifact.name,
    }

    def persist():
        temporary = report.with_suffix(".new")
        temporary.write_text(json.dumps(result, indent=2) + "\n")
        os.replace(temporary, report)

    persist()
    rows, cpu, llm_cpu = [], [], []
    history = frozenset(value["history"])
    cases = history | frozenset(value["queries"])
    expected_reasons = {}
    mutex, finished, start = Lock(), Event(), Barrier(10)
    context = ssl.create_default_context(cafile=str(ROOT / "deploy/local/tls/dev.crt"))

    def cpu_sample():
        while not finished.is_set():
            since = time.monotonic() - began
            sample = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.Name}} {{.CPUPerc}}",
                    "fk-stage9-fk-ai-embedding-1",
                    "fk-stage9-fk-ai-llm-1",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if sample.returncode == 0:
                for line in sample.stdout.splitlines():
                    match = re.fullmatch(
                        r"(fk-stage9-fk-ai-(embedding|llm)-1) (\d+(?:\.\d+)?)%", line.strip()
                    )
                    if match:
                        collection = cpu if match[2] == "embedding" else llm_cpu
                        collection.append(
                            {
                                "elapsed_seconds": round(time.monotonic() - began, 4),
                                "sample_start_seconds": round(since, 4),
                                "cpu_percent": float(match[3]),
                            }
                        )
            finished.wait(2)

    began = time.monotonic()
    sampler = Thread(target=cpu_sample, daemon=True)
    try:
        result["before"] = probe(value)
        if value["phase"] == "INDEXING":
            assert result["before"]["index_status"] == "PROCESSING"
            assert 0 < result["before"]["vectors"] < 10000
        else:
            assert result["before"]["index_status"] == "COMPLETED"
            assert result["before"]["vectors"] == 10000
        with httpx.Client(
            base_url=BASE,
            verify=context,
            trust_env=False,
            follow_redirects=False,
            timeout=5,
            headers={"Cookie": COOKIE_NAME + "=" + value["tokens"][0]},
        ) as client:
            response = client.get("/api/v1/decisions?limit=50")
            assert response.status_code == 200
            registry = response.json()
            assert len(registry) == 50
            assert all(r["conflict_id"] in value["history"] for r in registry)
            decision_ids = [r["id"] for r in registry[:10]]
            for identifier in decision_ids:
                UUID(identifier)
            if mode == "retrieval":
                for identifier in value["queries"][:10]:
                    response = client.get("/api/v1/conflicts/" + identifier + "/similar-decisions")
                    assert response.status_code == 200
                    reason = retrieval_expectation(
                        response.json(), value["version_id"], value["target"], history
                    )
                    assert reason is not None, "Full-index preflight read is invalid"
                    expected_reasons[identifier] = reason
                result["preflight_recommendation_reasons"] = dict(
                    Counter(expected_reasons.values())
                )

        def reader(position):
            query, decision = value["queries"][position], decision_ids[position]
            endpoints = {
                "conflict_list": "/api/v1/conflicts?limit=50",
                "registry_list": "/api/v1/decisions?limit=50",
                "decision_detail": "/api/v1/decisions/" + decision,
                "review_context": "/api/v1/conflicts/" + query + "/review-context",
                "conflict_detail": "/api/v1/conflicts/" + query,
            }
            if mode == "retrieval":
                endpoints = {
                    "similar_decisions": "/api/v1/conflicts/" + query + "/similar-decisions",
                    "recommendation": "/api/v1/conflicts/" + query + "/recommendation",
                    "registry_list": endpoints["registry_list"],
                    "review_context": endpoints["review_context"],
                    "decision_detail": endpoints["decision_detail"],
                }
            with httpx.Client(
                base_url=BASE,
                verify=context,
                trust_env=False,
                follow_redirects=False,
                timeout=5,
                headers={"Cookie": COOKIE_NAME + "=" + value["tokens"][position]},
            ) as client:
                start.wait(timeout=10)
                for _ in range(10):
                    for category, path in endpoints.items():
                        row = observe(
                            client,
                            category,
                            path,
                            query,
                            decision,
                            history,
                            cases,
                            value["version_id"],
                            value["target"],
                            expected_reasons.get(query),
                        )
                        with mutex:
                            rows.append(row)

        result["request_window_started_at"] = datetime.now(UTC).isoformat()
        began = time.monotonic()
        sampler.start()
        with ThreadPoolExecutor(10) as pool:
            list(pool.map(reader, range(10)))
        result["request_window_ended_at"] = datetime.now(UTC).isoformat()
        result["request_window_seconds"] = round(time.monotonic() - began, 4)
        finished.set()
        sampler.join(timeout=10)
        result["duration_seconds"] = round(time.monotonic() - began, 4)
        result["after"] = probe(value)
        result["immutable_history_preserved"] = (
            result["before"]["business_digests"] == result["after"]["business_digests"]
        )
    except Exception as error:
        result["error_code"] = type(error).__name__[:64]
    finally:
        finished.set()
        if sampler.is_alive():
            sampler.join(timeout=10)
        result.update(
            measurements=rows,
            embedding_cpu_samples=cpu,
            llm_cpu_samples=llm_cpu,
            requests=len(rows),
        )
        result["invalid_responses"] = sum(not r["valid"] for r in rows)
        result["outcomes"] = dict(
            Counter(r["error_code"] or "HTTP_" + str(r["status_code"]) for r in rows)
        )
        result["endpoint_p95_seconds"] = {
            endpoint: round(
                sorted(r["seconds"] for r in rows if r["endpoint"] == endpoint)[
                    math.ceil(sum(r["endpoint"] == endpoint for r in rows) * 0.95) - 1
                ],
                6,
            )
            for endpoint in {r["endpoint"] for r in rows}
        }
        result["passed"] = (
            len(rows) == 500
            and len(result["endpoint_p95_seconds"]) == 5
            and result["invalid_responses"] == 0
            and all(r["error_code"] is None for r in rows)
            and all(
                sum(r["endpoint"] == e for r in rows) == 100 for e in result["endpoint_p95_seconds"]
            )
            and "error_code" not in result
            and result.get("immutable_history_preserved") is True
            and result.get("after", {}).get("index_status") in {"PROCESSING", "COMPLETED"}
            and (
                activity == "none"
                or any(
                    s["cpu_percent"] >= 10
                    and s["elapsed_seconds"] <= result.get("request_window_seconds", 0)
                    for s in (cpu if activity == "embedding" else llm_cpu)
                )
            )
            and all(t <= 1 for t in result["endpoint_p95_seconds"].values())
        )
        persist()
    print(
        json.dumps(
            {
                "report": str(report.relative_to(ROOT)),
                "passed": result["passed"],
                "requests": len(rows),
                "endpoint_p95_seconds": result["endpoint_p95_seconds"],
            }
        )
    )
    if not result["passed"]:
        raise SystemExit("Actual core load failed; observations preserved, target unchanged")


if __name__ == "__main__":
    main()
