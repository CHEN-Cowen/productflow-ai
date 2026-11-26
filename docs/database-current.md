# ProductFlow AI 当前数据库结构

> 来源：`backend/db.py` 的 `SCHEMA` 与 `MIGRATIONS`。SQLite，原生 SQL，幂等迁移。

## 表清单

### meta
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL

### products（商品主档）
| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | 商品编号（大写字母/数字/短横线） |
| name | TEXT NOT NULL | 商品名称 |
| category_id | TEXT NOT NULL DEFAULT 'BAG' | 品类模板 ID |
| brand / origin / description | TEXT | 品牌/产地/描述 |
| status | TEXT DEFAULT 'draft' | draft / confirmed |
| created_at / updated_at | TEXT | ISO 时间 |

### categories（品类模板 = CategorySchema 载体）
| 列 | 类型 |
| --- | --- |
| id | TEXT PK |
| name | TEXT |
| version | INTEGER |
| schema_json | TEXT（attributes: key/label/type/unit/required/critical/allowed_values） |
| is_builtin | INTEGER |
| created_at / updated_at | TEXT |

### category_versions
- `category_id` + `version` 联合主键，`schema_json`、`created_at`

### skus
- `id` PK、`product_id` FK、`sku_code`、`attributes_json`、`created_at`
- UNIQUE(product_id, sku_code)

### sources（原始资料 SourceFile）
- id, product_id, sku_id, name, mime, size, sha256, kind(document/image), purpose(reference/spec/marketing), view_angle, review_status(pending/confirmed/rejected), status(stored), created_at

### imports（导入任务 ImportJob，抽取/异常内联 JSON）
- id, product_id, category, category_id, candidates(JSON), issues_json(JSON), source_ids_json(JSON), blocks_json(JSON), warnings_json(JSON), status(reviewing/confirmed/rejected), error, created_at, updated_at

### product_versions（商品不可变版本）
- id(自增), product_id, import_id, category, category_id, version, fields(JSON), provenance_json(JSON), sku, note, created_by, created_at

### plans（内容策划 PlanningTask，无版本）
- id, product_id, version_id, scene, source_ids, script(JSON), channel, audience, content_type, content_json(JSON), status(draft/confirmed), blocked_json, parent_plan_id, reused_outputs_json, created_at, updated_at

### outputs（生成资产）
- id, plan_id, kind(image/video), filename, status(pending/approved/rejected/…), note, mime, size, provider, model, prompt, params_json, error, attempt, source_output_id, created_at

### reviews（人工操作记录 = AuditLog 雏形）
- id, target_type, target_id, action, note, payload_json, reviewer, created_at

### workflow_runs（工作流执行记录）
- id, task_id, product_id, workflow_type, status, steps_json(JSON), error, error_code, created_at, finished_at

### generation_attempts（生成尝试 = AIExecutionLog 雏形）
- id, plan_id, kind, attempt, status, prompt, params_json, provider, model, error_code, error, request_id, output_id, created_at

### batch_jobs
- id, status, results_json, created_at, updated_at

### reference_tags（旧版视角，保留不删）
- source_id PK, angle

## 索引
- `idx_sources_product(product_id)`
- `idx_versions_product(product_id, version)`
- `idx_plans_product(product_id)`
- `idx_outputs_plan(plan_id)`
- `idx_runs_task(task_id)`

## 迁移机制
`init_db()`：`executescript(SCHEMA)` → `_add_missing_columns`（按 `MIGRATIONS` 表补列）→ `_backfill`（回填时间戳、文件大小、旧视角迁移）→ `_seed_categories`（内置模板 + 模板版本）。重复执行安全。
