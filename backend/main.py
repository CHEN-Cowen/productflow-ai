"""FastAPI 入口：启动时执行幂等迁移，挂载 REST API 与可选的构建后前端。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import router
from .errors import ApiError


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    config.configure(data_dir)
    db.init_db()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(title="ProductFlow AI", version="0.3.0",
                  description="商品数据治理与 AI 内容生产平台（本地模块化单体）")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                       "http://localhost:4173", "http://127.0.0.1:4173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"detail": {"message": exc.message, "code": exc.code, "hint": exc.hint}},
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("productflow").exception("unhandled error path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": {"message": "服务器内部错误", "code": "internal_error",
                                 "hint": "请查看后端日志后重试"}},
        )

    app.include_router(router)

    dist = config.BASE_DIR / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    return app


app = create_app()
