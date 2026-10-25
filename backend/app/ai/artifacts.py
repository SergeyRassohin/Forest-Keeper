"""Offline byte verification of the exact trusted model lock before loading."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from app.ai import baseline
from app.ai.contracts import AIError


def verify_component(root: Path, lock: Path, component: Literal["embedding", "llm"]) -> None:
    try:
        data = lock.read_bytes()
        if hashlib.sha256(data).hexdigest() != baseline.ARTIFACT_LOCK_SHA256:
            raise AIError("AI_ARTIFACT_LOCK_MISMATCH")
        spec = json.loads(data)[component]
        expected_model, expected_revision = (
            (baseline.EMBEDDING_MODEL, baseline.EMBEDDING_REVISION)
            if component == "embedding"
            else (baseline.LLM_MODEL, baseline.LLM_REVISION)
        )
        if spec["repository"] != expected_model or spec["revision"] != expected_revision:
            raise AIError("AI_MODEL_IDENTITY_MISMATCH")
        directory = (root / component).resolve(strict=True)
        if (root / component).is_symlink():
            raise AIError("AI_ARTIFACT_PATH_INVALID")
        allowed_files = {entry["path"] for entry in spec["files"]}
        allowed_dirs = {
            parent.as_posix()
            for name in allowed_files
            for parent in PurePosixPath(name).parents
            if parent.as_posix() != "."
        }
        for candidate in directory.rglob("*"):
            name = candidate.relative_to(directory).as_posix()
            if candidate.is_symlink() or not (
                (candidate.is_file() and name in allowed_files)
                or (candidate.is_dir() and name in allowed_dirs)
            ):
                raise AIError("AI_ARTIFACT_UNEXPECTED_FILE")
        for entry in spec["files"]:
            relative = PurePosixPath(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise AIError("AI_ARTIFACT_PATH_INVALID")
            candidate = directory.joinpath(*relative.parts)
            if (
                candidate.is_symlink()
                or not candidate.resolve(strict=True).is_relative_to(directory)
                or not candidate.is_file()
                or candidate.stat().st_size != entry["size"]
            ):
                raise AIError("AI_ARTIFACT_MISMATCH")
            with candidate.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            if checksum != entry["sha256"]:
                raise AIError("AI_ARTIFACT_MISMATCH")
    except AIError:
        raise
    except (OSError, KeyError, TypeError, ValueError):
        raise AIError("AI_ARTIFACT_UNAVAILABLE") from None
