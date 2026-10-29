"""Trusted server operator only; no new HTTP permission or role-based scope inference."""

import argparse
import json
from uuid import UUID

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import Settings
from app.common.database import make_engine
from app.similarity.jobs import activate_version, recover_indexes
from app.similarity.models import IndexRun, RetrievalState
from app.similarity.provider import ProviderError
from app.similarity.service import start_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "activate"])
    parser.add_argument(
        "--revision", choices=["test-v1", "test-v2", "qwen-demo-v1"], default="test-v1"
    )
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--version", type=UUID)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    settings = Settings()  # type: ignore[call-arg]
    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            if args.action == "start":
                run = start_run(
                    session,
                    settings,
                    args.revision,
                    activate=args.activate,
                    batch_size=args.batch_size,
                )
                session.commit()
                print(json.dumps({"run_id": str(run.id), "version_id": str(run.version_id)}))
            elif args.action == "activate":
                if args.version is None:
                    parser.error("--version required")
                activate_version(session, args.version)
                session.commit()
            else:
                state = session.get(RetrievalState, 1)
                print(
                    json.dumps(
                        {
                            "active_version": str(state.active_version_id)
                            if state and state.active_version_id
                            else None,
                            "runs": [
                                {
                                    k: str(getattr(r, k))
                                    for k in (
                                        "id",
                                        "version_id",
                                        "status",
                                        "processed",
                                        "indexed",
                                        "skipped",
                                        "last_decision_id",
                                        "error_code",
                                    )
                                }
                                for r in session.scalars(
                                    select(IndexRun).order_by(IndexRun.created_at.desc()).limit(20)
                                )
                            ],
                        }
                    )
                )
        if args.action == "start":
            with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
                recover_indexes(settings, redis)
    except ProviderError as error:
        parser.exit(2, str(error) + "\n")
    except Exception:
        parser.exit(2, "RETRIEVAL_OPERATOR_UNAVAILABLE\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
