"""Qwen batch inference outside database transactions, locks and connection pools."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.admission import prefix
from app.ai.contracts import semantic_context
from app.common.basis_lock import Budget, basis_lock
from app.common.config import Settings
from app.common.database import make_engine
from app.decisions.models import Decision
from app.decisions.service import digest
from app.similarity.context import COMPATIBILITY, context
from app.similarity.models import DecisionEmbedding, IndexItem, IndexRun, RetrievalVersion
from app.similarity.provider import ProviderError, QwenProvider, permitted, vector_hash
from app.similarity.service import audit, configuration, eligible


@dataclass(frozen=True)
class Planned:
    decision_id: UUID
    snapshot_hash: str
    reason: str
    features: dict[str, Any] | None


def execute(identifier: UUID, settings: Settings, *, max_batches: int | None = None) -> None:
    from app.similarity.jobs import activate_version, lock_key, missing

    if not permitted(settings) or settings.similarity_provider != "qwen-demo":
        raise ProviderError("PROVIDER_UNAVAILABLE")
    engine = make_engine(settings)
    token = uuid4().hex
    expected = token.encode()
    try:
        with Session(engine) as lookup:
            Budget().arm(lookup)
            version_id = lookup.scalar(select(IndexRun.version_id).where(IndexRun.id == identifier))
        if version_id is None:
            return
        lease_key = prefix(settings) + ":index-lease:" + version_id.hex
        with Redis.from_url(
            settings.redis_url.get_secret_value(), socket_connect_timeout=0.5, socket_timeout=0.5
        ) as redis:
            if not redis.set(lease_key, token, nx=True, ex=150):
                return

            def renew() -> bool:
                return bool(
                    redis.eval(
                        "if redis.call('get',KEYS[1]) == ARGV[1] then "
                        "return redis.call('expire',KEYS[1],150) end; return 0",
                        1,
                        lease_key,
                        token,
                    )
                )

            try:
                batches = 0
                while renew():
                    # Extract frozen bounded input and commit only technical start metadata.
                    with Session(engine) as session:
                        budget = Budget()
                        basis_lock(session, budget=budget)
                        run = session.get(IndexRun, identifier, with_for_update=True)
                        if run is None or run.status not in {"QUEUED", "PROCESSING"}:
                            return
                        if run.version_id != version_id:
                            raise ProviderError("UNSUPPORTED_VERSION")
                        version = session.get(RetrievalVersion, run.version_id)
                        if version is None or version.config != configuration("qwen-demo-v1"):
                            raise ProviderError("UNSUPPORTED_VERSION")
                        if not 1 <= run.batch_size <= 8:
                            raise ProviderError("INVALID_BATCH_SIZE")
                        if run.status == "QUEUED":
                            run.status = "PROCESSING"
                            audit(session, run.version_id, "BACKFILL_STARTED", run_id=str(run.id))
                        rows = list(
                            session.scalars(
                                missing(run.version_id).order_by(Decision.id).limit(run.batch_size)
                            )
                        )
                        if not rows:
                            if run.activate:
                                activate_version(session, run.version_id)
                            run.status = "COMPLETED"
                            audit(
                                session,
                                run.version_id,
                                "BACKFILL_COMPLETED",
                                run_id=str(run.id),
                                processed=run.processed,
                                indexed=run.indexed,
                                skipped=run.skipped,
                            )
                            budget.prepare_commit(session)
                            session.commit()
                            return
                        version_id = run.version_id
                        plans = []
                        for row in rows:
                            reason, features = "INDEXED", None
                            live = session.scalar(
                                eligible()
                                .with_only_columns(Decision.id)
                                .where(Decision.id == row.id)
                            )
                            if live is None:
                                reason = "OUTCOME_OR_LIFECYCLE_EXCLUDED"
                            else:
                                try:
                                    features = context(row.context_snapshot, row)
                                    semantic_context(features)
                                except ProviderError as error:
                                    reason = str(error)
                                except ValidationError:
                                    reason = "AI_INPUT_MINIMIZATION_REQUIRED"
                            plans.append(
                                Planned(
                                    row.id,
                                    digest(row.context_snapshot),
                                    reason,
                                    features if reason == "INDEXED" else None,
                                )
                            )
                        budget.prepare_commit(session)
                        session.commit()
                    # Session/connection/basis gate are all released before HTTP inference.
                    inputs = [plan.features for plan in plans if plan.features is not None]
                    vectors = QwenProvider(settings).embed_many(inputs) if inputs else []
                    computed = {
                        plan.decision_id: vector
                        for plan, vector in zip(
                            [plan for plan in plans if plan.features is not None],
                            vectors,
                            strict=True,
                        )
                    }
                    if not renew():
                        return
                    with Session(engine) as session:
                        budget = Budget()
                        basis_lock(session, budget=budget)
                        schema = session.scalar(text("SELECT current_schema()"))
                        if not session.scalar(
                            text("SELECT pg_try_advisory_xact_lock(:key)"),
                            {
                                "key": lock_key(version_id, schema),
                            },
                        ):
                            return
                        run = session.get(IndexRun, identifier, with_for_update=True)
                        if run is None or run.status not in {"QUEUED", "PROCESSING"}:
                            return
                        for plan in plans:
                            if session.get(IndexItem, (version_id, plan.decision_id)) is not None:
                                continue
                            row = session.get(Decision, plan.decision_id)
                            if row is None or digest(row.context_snapshot) != plan.snapshot_hash:
                                raise ProviderError("CORRUPT_EVIDENCE")
                            reason = plan.reason
                            live = session.scalar(
                                eligible()
                                .with_only_columns(Decision.id)
                                .where(Decision.id == row.id)
                            )
                            if live is None:
                                reason = "OUTCOME_OR_LIFECYCLE_EXCLUDED"
                            if reason == "INDEXED" and plan.features is not None:
                                vector = computed[plan.decision_id]
                                session.add(
                                    DecisionEmbedding(
                                        decision_id=row.id,
                                        version_id=version_id,
                                        **{key: plan.features[key] for key in COMPATIBILITY},
                                        embedding=vector,
                                        features=plan.features,
                                        feature_hash=digest(plan.features),
                                        input_hash=digest(plan.features),
                                        vector_hash=vector_hash(vector),
                                    )
                                )
                            session.add(
                                IndexItem(
                                    version_id=version_id,
                                    decision_id=row.id,
                                    reason=reason,
                                )
                            )
                            run.processed += 1
                            run.indexed += reason == "INDEXED"
                            run.skipped += reason != "INDEXED"
                            run.last_decision_id = row.id
                        budget.prepare_commit(session)
                        session.commit()
                    batches += 1
                    if max_batches is not None and batches >= max_batches:
                        return
            except Exception:
                if redis.get(lease_key) == expected:
                    with Session(engine) as session:
                        budget = Budget()
                        basis_lock(session, budget=budget)
                        run = session.get(IndexRun, identifier, with_for_update=True)
                        if run is not None and run.status in {"QUEUED", "PROCESSING"}:
                            run.status, run.error_code = "FAILED", "INDEXING_FAILED"
                            audit(session, run.version_id, "BACKFILL_FAILED", run_id=str(run.id))
                            budget.prepare_commit(session)
                            session.commit()
            finally:
                redis.eval(
                    "if redis.call('get',KEYS[1]) == ARGV[1] then "
                    "return redis.call('del',KEYS[1]) end; return 0",
                    1,
                    lease_key,
                    token,
                )
    except Exception:
        logging.getLogger(__name__).warning("QWEN_BACKFILL_UNAVAILABLE")
    finally:
        engine.dispose()
