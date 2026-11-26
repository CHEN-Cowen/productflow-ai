"""SQLite 连接、可重复的非破坏性迁移与通用数据访问工具。

只使用绑定参数执行 SQL；启动时补齐缺失列并回填旧数据，不删除旧表或旧行。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    category_id TEXT NOT NULL DEFAULT 'BAG',
    brand TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    schema_json TEXT NOT NULL,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS category_versions (
    category_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    schema_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (category_id, version)
);

CREATE TABLE IF NOT EXISTS skus (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL REFERENCES products(id),
    sku_code TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE (product_id, sku_code)
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL REFERENCES products(id),
    sku_id TEXT,
    name TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'document',
    purpose TEXT NOT NULL DEFAULT 'reference',
    view_angle TEXT NOT NULL DEFAULT '',
    review_status TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'stored',
    asset_type TEXT NOT NULL DEFAULT 'raw',
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS imports (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL,
    category TEXT NOT NULL,
    category_id TEXT NOT NULL DEFAULT '',
    candidates TEXT NOT NULL DEFAULT '{}',
    issues_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    blocks_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'reviewing',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL,
    import_id TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    category_id TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    fields TEXT NOT NULL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    sku TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL,
    version_id INTEGER NOT NULL,
    current_version_id INTEGER NOT NULL DEFAULT 0,
    scene TEXT NOT NULL,
    source_ids TEXT NOT NULL DEFAULT '[]',
    script TEXT NOT NULL DEFAULT '{}',
    channel TEXT NOT NULL DEFAULT '',
    audience TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    blocked_json TEXT NOT NULL DEFAULT '[]',
    parent_plan_id TEXT NOT NULL DEFAULT '',
    reused_outputs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS planning_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    planning_task_id TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    strategy_json TEXT NOT NULL DEFAULT '{}',
    creative_json TEXT NOT NULL DEFAULT '{}',
    image_plan_json TEXT NOT NULL DEFAULT '{}',
    video_plan_json TEXT NOT NULL DEFAULT '{}',
    approval_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS outputs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    plan_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT NOT NULL DEFAULT '',
    mime TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    attempt INTEGER NOT NULL DEFAULT 1,
    source_output_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    reviewer TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    task_id TEXT NOT NULL,
    product_id TEXT NOT NULL DEFAULT '',
    workflow_type TEXT NOT NULL,
    status TEXT NOT NULL,
    steps_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS generation_attempts (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL DEFAULT '',
    output_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    results_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ai_execution_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    task_id TEXT NOT NULL DEFAULT '',
    step_name TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    model_version TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    input_summary TEXT NOT NULL DEFAULT '',
    output_summary TEXT NOT NULL DEFAULT '',
    token_usage_json TEXT NOT NULL DEFAULT '{}',
    cost REAL NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error_code TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_snapshot TEXT NOT NULL DEFAULT '',
    output_snapshot TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS extraction_records (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    import_job_id TEXT NOT NULL DEFAULT '',
    source_file_id TEXT NOT NULL DEFAULT '',
    product_id TEXT NOT NULL DEFAULT '',
    raw_field TEXT NOT NULL DEFAULT '',
    raw_value TEXT NOT NULL DEFAULT '',
    mapped_field TEXT NOT NULL DEFAULT '',
    extracted_value TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    source_location TEXT NOT NULL DEFAULT '{}',
    model_name TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS data_issues (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT NOT NULL DEFAULT '',
    attribute_key TEXT NOT NULL DEFAULT '',
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    source_records TEXT NOT NULL DEFAULT '[]',
    issue_description TEXT NOT NULL DEFAULT '',
    resolution_status TEXT NOT NULL DEFAULT 'open',
    resolution_value TEXT NOT NULL DEFAULT '',
    resolved_by TEXT NOT NULL DEFAULT '',
    resolved_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    operator_id TEXT NOT NULL DEFAULT 'user',
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_value TEXT NOT NULL DEFAULT '',
    after_value TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reference_tags (
    source_id TEXT PRIMARY KEY,
    angle TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_product ON sources(product_id);
CREATE INDEX IF NOT EXISTS idx_versions_product ON product_versions(product_id, version);
CREATE INDEX IF NOT EXISTS idx_plans_product ON plans(product_id);
CREATE INDEX IF NOT EXISTS idx_planning_versions_task ON planning_versions(planning_task_id);
CREATE INDEX IF NOT EXISTS idx_outputs_plan ON outputs(plan_id);
CREATE INDEX IF NOT EXISTS idx_runs_task ON workflow_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_extractions_import ON extraction_records(import_job_id);
CREATE INDEX IF NOT EXISTS idx_issues_product ON data_issues(product_id);
CREATE INDEX IF NOT EXISTS idx_ai_logs_task ON ai_execution_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);
"""

MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "products": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("category_id", "TEXT NOT NULL DEFAULT 'BAG'"),
        ("brand", "TEXT NOT NULL DEFAULT ''"),
        ("origin", "TEXT NOT NULL DEFAULT ''"),
        ("description", "TEXT NOT NULL DEFAULT ''"),
        ("status", "TEXT NOT NULL DEFAULT 'draft'"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "sources": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("sku_id", "TEXT"),
        ("size", "INTEGER NOT NULL DEFAULT 0"),
        ("sha256", "TEXT NOT NULL DEFAULT ''"),
        ("kind", "TEXT NOT NULL DEFAULT 'document'"),
        ("purpose", "TEXT NOT NULL DEFAULT 'reference'"),
        ("view_angle", "TEXT NOT NULL DEFAULT ''"),
        ("review_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("status", "TEXT NOT NULL DEFAULT 'stored'"),
        ("asset_type", "TEXT NOT NULL DEFAULT 'raw'"),
        ("tags", "TEXT NOT NULL DEFAULT '[]'"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "imports": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("category_id", "TEXT NOT NULL DEFAULT ''"),
        ("issues_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("source_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("blocks_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("warnings_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("status", "TEXT NOT NULL DEFAULT 'reviewing'"),
        ("error", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "product_versions": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("category_id", "TEXT NOT NULL DEFAULT ''"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("provenance_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("note", "TEXT NOT NULL DEFAULT ''"),
        ("created_by", "TEXT NOT NULL DEFAULT 'user'"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "plans": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("current_version_id", "INTEGER NOT NULL DEFAULT 0"),
        ("channel", "TEXT NOT NULL DEFAULT ''"),
        ("audience", "TEXT NOT NULL DEFAULT ''"),
        ("content_type", "TEXT NOT NULL DEFAULT ''"),
        ("content_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("status", "TEXT NOT NULL DEFAULT 'draft'"),
        ("blocked_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("parent_plan_id", "TEXT NOT NULL DEFAULT ''"),
        ("reused_outputs_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "outputs": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("mime", "TEXT NOT NULL DEFAULT ''"),
        ("size", "INTEGER NOT NULL DEFAULT 0"),
        ("provider", "TEXT NOT NULL DEFAULT ''"),
        ("model", "TEXT NOT NULL DEFAULT ''"),
        ("prompt", "TEXT NOT NULL DEFAULT ''"),
        ("params_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("error", "TEXT NOT NULL DEFAULT ''"),
        ("attempt", "INTEGER NOT NULL DEFAULT 1"),
        ("source_output_id", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "workflow_runs": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("product_id", "TEXT NOT NULL DEFAULT ''"),
    ],
    "skus": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
    ],
    "reviews": [
        ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
    ],
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(config.db_path(), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    return db


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rows(db: sqlite3.Connection, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def one(db: sqlite3.Connection, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    row = db.execute(sql, params).fetchone()
    return dict(row) if row else None


def loads(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(db: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = _columns(db, table)
        if not existing:
            continue
        for name, ddl in columns:
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _backfill(db: sqlite3.Connection) -> None:
    stamp = now()
    db.execute("UPDATE products SET created_at=? WHERE created_at=''", (stamp,))
    db.execute("UPDATE products SET updated_at=? WHERE updated_at=''", (stamp,))
    db.execute("UPDATE sources SET created_at=? WHERE created_at=''", (stamp,))
    db.execute(
        "UPDATE sources SET kind='image' WHERE kind='document' AND mime LIKE 'image/%'"
    )
    # 兼容旧数据：补齐历史资料的文件大小，保证预览时能校验原件完整性
    for row in db.execute("SELECT id, size FROM sources WHERE size=0").fetchall():
        candidate = next(iter(config.uploads_dir().glob(row["id"] + ".*")), None)
        if candidate is None:
            legacy = config.uploads_dir() / row["id"]
            candidate = legacy if legacy.is_file() else None
        if candidate and candidate.is_file():
            db.execute("UPDATE sources SET size=? WHERE id=?", (candidate.stat().st_size, row["id"]))
    # 旧版 reference_tags 视角迁移到 sources.view_angle，保留旧表不删除
    if _columns(db, "reference_tags"):
        db.execute(
            "UPDATE sources SET view_angle=COALESCE(("
            "SELECT angle FROM reference_tags WHERE reference_tags.source_id=sources.id), '') "
            "WHERE view_angle='' AND EXISTS (SELECT 1 FROM reference_tags WHERE reference_tags.source_id=sources.id)"
        )
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','2')")


def _seed_categories(db: sqlite3.Connection) -> None:
    from .templates import BUILTIN

    stamp = now()
    for key, schema in BUILTIN.items():
        existing = one(db, "SELECT id FROM categories WHERE id=?", (key,))
        if existing is None:
            db.execute(
                "INSERT INTO categories(id,name,version,schema_json,is_builtin,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (key, schema["category_name"], 1, dumps(schema), 1, stamp, stamp),
            )
        row = one(db, "SELECT version, schema_json FROM categories WHERE id=?", (key,))
        if row and not one(
            db, "SELECT 1 FROM category_versions WHERE category_id=? AND version=?",
            (key, row["version"]),
        ):
            db.execute(
                "INSERT INTO category_versions(category_id,version,schema_json,created_at) VALUES(?,?,?,?)",
                (key, row["version"], row["schema_json"], stamp),
            )


def _seed_tenants(db: sqlite3.Connection) -> None:
    stamp = now()
    if one(db, "SELECT 1 FROM tenants WHERE id='default'") is None:
        db.execute(
            "INSERT INTO tenants(id,name,status,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("default", "默认租户", "active", stamp, stamp),
        )


def init_db() -> None:
    config.ensure_dirs()
    with session() as db:
        db.executescript(SCHEMA)
        _add_missing_columns(db)
        _backfill(db)
        _seed_categories(db)
        _seed_tenants(db)
