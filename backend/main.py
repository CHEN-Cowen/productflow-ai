import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .workflow import register_workflow

app = FastAPI(title="ProductFlow AI")
root = Path(os.environ.get("PRODUCTFLOW_DATA", Path(__file__).resolve().parent.parent / "data"))
uploads = root / "uploads"
uploads.mkdir(parents=True, exist_ok=True)
LIMIT = 10 * 1024 * 1024

with closing(sqlite3.connect(root / "productflow.sqlite3")) as db:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id),
            name TEXT NOT NULL, mime TEXT NOT NULL
        );
    """)


def connection():
    db = sqlite3.connect(root / "productflow.sqlite3")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


class Draft(BaseModel):
    id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{0,31}$")
    name: str = Field(min_length=1, max_length=120)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/products", status_code=201)
def create_product(draft: Draft):
    name = draft.name.strip()
    if not name:
        raise HTTPException(422, "请输入商品名称")
    with closing(connection()) as db:
        try:
            with db:
                db.execute("INSERT INTO products VALUES (?, ?)", (draft.id, name))
        except sqlite3.IntegrityError as error:
            raise HTTPException(409, "该商品编号已存在") from error
    return get_product(draft.id)


@app.get("/api/v1/products/{product_id}")
def get_product(product_id: str):
    with closing(connection()) as db:
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            raise HTTPException(404, "找不到该商品")
        sources = db.execute(
            "SELECT id, name, mime FROM sources WHERE product_id = ? ORDER BY rowid", (product_id,)
        ).fetchall()
        approved = db.execute(
            "SELECT 1 FROM product_versions WHERE product_id = ?", (product_id,)
        ).fetchone()
    return {**dict(product), "status": "approved" if approved else "draft",
            "sources": [dict(row) for row in sources]}


@app.post("/api/v1/products/{product_id}/sources", status_code=201)
def upload_source(product_id: str, file: UploadFile = File(...)):
    get_product(product_id)
    content = file.file.read(LIMIT + 1)
    if len(content) > LIMIT:
        raise HTTPException(413, "文件大小不能超过 10 MB")
    signatures = {
        b"%PDF-": "application/pdf",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"\xff\xd8\xff": "image/jpeg",
    }
    mime = next((mime for prefix, mime in signatures.items() if content.startswith(prefix)), None)
    if not mime:
        raise HTTPException(415, "请上传 PDF、PNG 或 JPEG 文件")
    source_id = uuid4().hex
    path = uploads / source_id
    name = (file.filename or "原始资料").replace("\\", "/").rsplit("/", 1)[-1]
    try:
        path.write_bytes(content)
        with closing(connection()) as db, db:
            db.execute("INSERT INTO sources VALUES (?, ?, ?, ?)", (source_id, product_id, name, mime))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"id": source_id, "name": name, "mime": mime}


@app.get("/api/v1/products/{product_id}/sources/{source_id}")
def get_source(product_id: str, source_id: str):
    with closing(connection()) as db:
        source = db.execute(
            "SELECT * FROM sources WHERE id = ? AND product_id = ?", (source_id, product_id)
        ).fetchone()
    if source is None or not (uploads / source_id).is_file():
        raise HTTPException(404, "找不到该资料")
    return FileResponse(
        uploads / source_id, media_type=source["mime"], filename=source["name"],
        content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"},
    )


register_workflow(app, connection, uploads)
