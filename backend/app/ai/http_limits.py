"""Bound only the small public AI JSON bodies; core/import routes remain independent."""

import asyncio

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.errors import ApiError


class AIRequestLimits:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.pending = asyncio.BoundedSemaphore(16)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        bounded = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and (
                path.startswith("/api/v1/conflicts/")
                and (path.endswith("/ai-explanation") or "/ai-explanations/" in path)
            )
        )
        if not bounded:
            await self.app(scope, receive, send)
            return

        async def reject(status: int, code: str) -> None:
            await JSONResponse(
                ApiError(status, code, "AI-запрос отклонён. Ручное рассмотрение доступно").body(),
                status_code=status,
                headers={"Cache-Control": "no-store", "Connection": "close"},
            )(scope, receive, send)

        try:
            await asyncio.wait_for(self.pending.acquire(), timeout=0.01)
        except TimeoutError:
            await reject(429, "AI_BUSY")
            return
        chunks, size = [], 0
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > 4096:
                        await reject(413, "AI_INPUT_TOO_LARGE")
                        return
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(408, "AI_INPUT_TIMEOUT")
            return
        finally:
            self.pending.release()
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, bounded_receive, send)
