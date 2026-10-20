import hashlib
import os
import re
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from app.common.errors import ApiError


def checked_filename(filename: str | None) -> tuple[str, str]:
    if (
        not filename
        or len(filename) > 255
        or filename in {".", ".."}
        or re.search(r"[\x00-\x1f\x7f/\\:]", filename)
    ):
        raise ApiError(422, "INVALID_FILENAME", "Недопустимое имя файла")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xml"}:
        raise ApiError(415, "UNSUPPORTED_FORMAT", "Поддерживаются CSV, XLSX и XML")
    return filename, suffix[1:].upper()


def file_checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def path(self, uri: str) -> Path:
        # Only our generated key can select a file; user filenames never enter paths.
        if not re.fullmatch(r"local:[0-9a-f]{32}", uri):
            raise ValueError("Invalid storage key")
        target = self.root / (uri[6:] + ".original")
        if target.is_symlink():
            raise ValueError("Invalid storage object")
        return target

    def save(self, batch_id: UUID, stream: BinaryIO, max_bytes: int) -> tuple[str, str]:
        uri = "local:" + batch_id.hex
        target = self.path(uri)
        created = False
        try:
            # Exclusive creation prevents both overwrite and following an existing symlink.
            with target.open("xb") as output:
                created = True
                size = 0
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ApiError(413, "FILE_TOO_LARGE", "Файл превышает допустимый размер")
                    output.write(chunk)
                if size == 0:
                    raise ApiError(422, "EMPTY_FILE", "Файл пуст")
                output.flush()
                os.fsync(output.fileno())
            target.chmod(0o400)
            # Hash the bytes on disk, rather than trusting a client or upload header.
            return uri, file_checksum(target)
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise

    def discard_unreferenced(self, uri: str) -> None:
        # Called only for this request's exclusively-created, uncommitted object.
        self.path(uri).unlink(missing_ok=True)
