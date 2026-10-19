from collections.abc import AsyncGenerator, Sequence
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from python_multipart.exceptions import MultipartParseError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.auth.dependencies import Cache, Config, Db, require_permission
from app.auth.models import AuditEvent, User
from app.common.errors import ApiError
from app.imports.jobs import enqueue_batch, recover_imports
from app.imports.models import ImportBatch, ImportErrorRecord, ImportStatus, RawRecord, SourceSystem
from app.imports.schemas import (
    ErrorView,
    ImportView,
    RawView,
    SourceCreate,
    SourceUpdate,
    SourceView,
)
from app.imports.service import audit_import
from app.imports.storage import LocalStorage, checked_filename

router = APIRouter(prefix="/api/v1", tags=["imports"])
SourceReader = Annotated[User, Depends(require_permission("source.view"))]
SourceManager = Annotated[User, Depends(require_permission("source.manage"))]
ImportReader = Annotated[User, Depends(require_permission("import.view"))]
ImportCreator = Annotated[User, Depends(require_permission("import.create"))]
ImportRetrier = Annotated[User, Depends(require_permission("import.retry"))]
PageSize = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


def source_or_404(session: Db, source_id: UUID) -> SourceSystem:
    source = session.get(SourceSystem, source_id)
    if source is None:
        raise ApiError(404, "SOURCE_NOT_FOUND", "Источник не найден")
    return source


def batch_or_404(session: Db, batch_id: UUID) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ApiError(404, "IMPORT_NOT_FOUND", "Пакет импорта не найден")
    return batch


@router.get("/sources", response_model=list[SourceView])
def sources(
    session: Db,
    actor: SourceReader,
    limit: PageSize = 50,
    offset: Offset = 0,
) -> Sequence[SourceSystem]:
    return session.scalars(
        select(SourceSystem).order_by(SourceSystem.code).offset(offset).limit(limit)
    ).all()


@router.get("/sources/{source_id}", response_model=SourceView)
def source_detail(source_id: UUID, session: Db, actor: SourceReader) -> SourceSystem:
    return source_or_404(session, source_id)


@router.post("/sources", response_model=SourceView, status_code=201)
def create_source(body: SourceCreate, session: Db, actor: SourceManager) -> SourceSystem:
    source = SourceSystem(**body.model_dump())
    session.add(source)
    try:
        session.flush()
        session.add(
            AuditEvent(
                event_type="SOURCE_CREATED",
                user_id=actor.id,
                object_type="SourceSystem",
                object_id=source.id,
                payload={},
            )
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError(409, "SOURCE_CODE_EXISTS", "Код источника уже используется") from None
    return source


@router.patch("/sources/{source_id}", response_model=SourceView)
def update_source(
    source_id: UUID,
    body: SourceUpdate,
    session: Db,
    actor: SourceManager,
) -> SourceSystem:
    source = source_or_404(session, source_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise ApiError(422, "INVALID_REQUEST", "Настройки не могут быть null")
        setattr(source, key, value)
    session.add(
        AuditEvent(
            event_type="SOURCE_UPDATED",
            user_id=actor.id,
            object_type="SourceSystem",
            object_id=source.id,
            payload={},
        )
    )
    session.commit()
    return source


@router.get("/imports", response_model=list[ImportView])
def imports(
    session: Db, actor: ImportReader, limit: PageSize = 50, offset: Offset = 0
) -> list[ImportView]:
    rows = session.execute(
        select(ImportBatch, SourceSystem.name)
        .join(SourceSystem)
        .order_by(
            ImportBatch.uploaded_at.desc(),
            ImportBatch.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return [ImportView.of(batch, name) for batch, name in rows]


@router.get("/imports/{batch_id}", response_model=ImportView)
def import_detail(batch_id: UUID, session: Db, actor: ImportReader) -> ImportView:
    batch = batch_or_404(session, batch_id)
    return ImportView.of(batch, source_or_404(session, batch.source_system_id).name)


@router.get("/imports/{batch_id}/records", response_model=list[RawView])
def records(
    batch_id: UUID,
    session: Db,
    actor: ImportReader,
    limit: PageSize = 50,
    offset: Offset = 0,
) -> Sequence[RawRecord]:
    batch_or_404(session, batch_id)
    return session.scalars(
        select(RawRecord)
        .where(RawRecord.import_batch_id == batch_id)
        .order_by(
            RawRecord.created_at,
            RawRecord.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/imports/{batch_id}/errors", response_model=list[ErrorView])
def errors(
    batch_id: UUID,
    session: Db,
    actor: ImportReader,
    limit: PageSize = 50,
    offset: Offset = 0,
) -> Sequence[ImportErrorRecord]:
    batch_or_404(session, batch_id)
    return session.scalars(
        select(ImportErrorRecord)
        .where(
            ImportErrorRecord.import_batch_id == batch_id,
        )
        .order_by(ImportErrorRecord.position_key, ImportErrorRecord.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.post("/imports", response_model=ImportView, status_code=201)
async def upload_import(
    request: Request,
    response: Response,
    session: Db,
    actor: ImportCreator,
    settings: Config,
    redis: Cache,
) -> ImportView:
    max_body = settings.import_max_bytes + 65_536
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > max_body):
        raise ApiError(413, "FILE_TOO_LARGE", "Файл превышает допустимый размер")
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise ApiError(415, "MULTIPART_REQUIRED", "Выберите файл для загрузки")
    too_large = False

    async def limited_stream() -> AsyncGenerator[bytes]:
        nonlocal too_large
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > max_body:
                too_large = True
                # MultiPartParser closes its temporary files for this exception.
                raise MultiPartException("Upload limit exceeded")
            yield chunk

    try:
        form = await MultiPartParser(
            request.headers,
            limited_stream(),
            max_files=1,
            max_fields=1,
            max_part_size=1024,
        ).parse()
    except (MultiPartException, MultipartParseError):
        raise ApiError(
            413 if too_large else 422,
            "FILE_TOO_LARGE" if too_large else "INVALID_UPLOAD",
            "Файл превышает допустимый размер" if too_large else "Некорректная загрузка",
        ) from None
    try:
        file, source_value = form.get("file"), form.get("source_id")
        if not isinstance(file, UploadFile) or not isinstance(source_value, str):
            raise ApiError(422, "INVALID_UPLOAD", "Укажите источник и файл")
        try:
            source_id = UUID(source_value)
        except ValueError:
            raise ApiError(422, "INVALID_SOURCE", "Неверный идентификатор источника") from None
        filename, file_format = checked_filename(file.filename)
        source = source_or_404(session, source_id)
        if source.status != "ACTIVE":
            raise ApiError(409, "SOURCE_INACTIVE", "Источник не активен")
        storage = LocalStorage(settings.import_storage_root)
        batch_id = uuid4()
        uri, checksum = await run_in_threadpool(
            storage.save,
            batch_id,
            file.file,
            settings.import_max_bytes,
        )
        batch = ImportBatch(
            id=batch_id,
            source_system_id=source.id,
            original_filename=filename,
            format=file_format,
            file_hash=checksum,
            storage_uri=uri,
            uploaded_by=actor.id,
        )
        session.add(batch)
        try:
            session.flush()
            audit_import(session, "IMPORT_UPLOADED", batch, actor.id)
            session.commit()
        except IntegrityError:
            session.rollback()
            storage.discard_unreferenced(uri)
            existing = session.scalar(
                select(ImportBatch).where(
                    ImportBatch.source_system_id == source_id,
                    ImportBatch.file_hash == checksum,
                    ImportBatch.retry_of_id.is_(None),
                )
            )
            if existing is None:
                raise ApiError(
                    409, "IMPORT_CONFLICT", "Не удалось зарегистрировать импорт"
                ) from None
            response.status_code = 200
            return ImportView.of(existing, source.name, duplicate=True)
        await run_in_threadpool(enqueue_batch, batch.id, session, redis, settings)
        session.refresh(batch)
        return ImportView.of(batch, source.name)
    finally:
        await form.close()


@router.post("/imports/{batch_id}/retry", response_model=ImportView, status_code=201)
def retry_import(
    batch_id: UUID,
    session: Db,
    actor: ImportRetrier,
    settings: Config,
    redis: Cache,
) -> ImportView:
    try:
        recover_imports(settings, redis)
    except Exception:
        raise ApiError(503, "QUEUE_UNAVAILABLE", "Очередь временно недоступна") from None
    old = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update())
    if old is None:
        raise ApiError(404, "IMPORT_NOT_FOUND", "Пакет импорта не найден")
    if old.status not in {ImportStatus.FAILED, ImportStatus.COMPLETED_WITH_ERRORS}:
        raise ApiError(409, "RETRY_NOT_ALLOWED", "Повтор доступен для неуспешного импорта")
    source = source_or_404(session, old.source_system_id)
    if source.status != "ACTIVE":
        raise ApiError(409, "SOURCE_INACTIVE", "Источник не активен")
    active = session.scalar(
        select(ImportBatch.id).where(
            ImportBatch.retry_of_id == old.id,
            ImportBatch.status.in_(
                [ImportStatus.NEW, ImportStatus.QUEUED, ImportStatus.PROCESSING]
            ),
        )
    )
    if active:
        raise ApiError(409, "RETRY_IN_PROGRESS", "Повторный импорт уже запущен")
    batch = ImportBatch(
        source_system_id=source.id,
        original_filename=old.original_filename,
        format=old.format,
        file_hash=old.file_hash,
        storage_uri=old.storage_uri,
        uploaded_by=actor.id,
        retry_of_id=old.id,
    )
    session.add(batch)
    session.flush()
    audit_import(session, "IMPORT_UPLOADED", batch, actor.id, {"retry_of_id": str(old.id)})
    session.commit()
    enqueue_batch(batch.id, session, redis, settings)
    session.refresh(batch)
    return ImportView.of(batch, source.name)
