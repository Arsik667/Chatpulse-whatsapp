"""FastAPI — тонкая обёртка над analyzer_core.

    POST /api/analyze  multipart/form-data, поле file (.txt или .zip) → JSON-отчёт
    GET  /api/health   для healthcheck в docker-compose

Приватность: файл целиком живёт в памяти процесса и выбрасывается сразу после
ответа — ни на диск, ни в логи он не попадает. Обычный `file: UploadFile` тут
не подходит: Starlette складывает загрузки больше 1 МБ во временный файл на
диске. Поэтому multipart разбираем сами — тем же парсером Starlette, но с
порогом «сброса на диск» выше лимита на размер запроса.
"""

import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from analyzer_core import DEFAULT_GAP_HOURS, ChatParseError, analyze_file

MAX_UPLOAD_MB = int(os.getenv("CHATPULSE_MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
# Фронтенд в dev-режиме и в Docker открывается на :5173 — больше никого не пускаем.
CORS_ORIGINS = os.getenv("CHATPULSE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")


class InMemoryMultiPartParser(MultiPartParser):
    # SpooledTemporaryFile держит данные в памяти, пока их меньше spool_max_size,
    # а потом переезжает на диск. Тело запроса мы сами обрезаем на MAX_UPLOAD_BYTES,
    # так что до порога дело не доходит и файл всегда остаётся в памяти.
    spool_max_size = MAX_UPLOAD_BYTES


app = FastAPI(
    title="ChatPulse API",
    description="Локальный анализатор экспортов WhatsApp. Файлы не сохраняются.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"])


def _too_large() -> HTTPException:
    return HTTPException(413, f"Файл больше {MAX_UPLOAD_MB} МБ. Попробуйте экспорт без медиа — это один .txt.")


async def _read_upload(request: Request) -> tuple[bytes, str]:
    """Достаёт из multipart-запроса поле file целиком в память."""
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(415, "Ожидается multipart/form-data с файлом в поле file.")
    # Браузер всегда присылает Content-Length — отказываем сразу, не читая тело.
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise _too_large()

    async def limited_body():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_UPLOAD_BYTES:  # на случай запросов без Content-Length
                raise _too_large()
            yield chunk

    parser = InMemoryMultiPartParser(request.headers, limited_body(), max_files=1, max_fields=5)
    try:
        form = await parser.parse()
    except MultiPartException as exc:
        raise HTTPException(400, f"Не удалось разобрать форму: {exc.message}") from exc

    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(400, "В запросе нет файла в поле file.")
        return await upload.read(), upload.filename or ""
    finally:
        await form.close()


# Разбираем multipart вручную, поэтому FastAPI сам не знает про поле file —
# описываем его для Swagger (/api/docs), чтобы там была кнопка загрузки.
UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {"type": "string", "format": "binary", "description": "Экспорт WhatsApp: .txt или .zip"},
                    },
                }
            }
        },
    }
}


@app.post("/api/analyze", openapi_extra=UPLOAD_OPENAPI)
async def analyze(
    request: Request,
    gap_hours: float = Query(DEFAULT_GAP_HOURS, gt=0, le=168, description="Пауза (ч), после которой начинается новый разговор"),
) -> dict:
    """Загрузить экспорт чата и получить все метрики одним JSON."""
    data, filename = await _read_upload(request)
    try:
        # Анализ — синхронный CPU-код; уносим в пул потоков, чтобы не блокировать event loop.
        return await run_in_threadpool(analyze_file, data, filename, gap_hours=gap_hours)
    except ChatParseError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "max_upload_mb": MAX_UPLOAD_MB}
