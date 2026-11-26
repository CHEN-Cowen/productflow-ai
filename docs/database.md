# ProductFlow AI 数据库设计

> 基于 `backend/db.py` 的幂等迁移。SQLite（MVP），原生 SQL；数据访问收敛在 `db.py`，为迁移 PostgreSQL 预留空间（业务层不写 SQLite 特有函数）。

## 迁移机制

`init_db()`：`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN`（`MIGRATIONS` 表）+ 回填 + 种子（内置品类、默认租户）。重复执行安全，不删除旧表/旧行。

## 租户隔离

所有私有数据表带 `tenant_id`（默认 `default`），写入时记录，读取时按当前租户过滤，跨租户访问抛 `TENANT_ACCESS_DENIED`。`tenants` 表管理租户。

## 表清单

### 治理与元数据
- `meta`：schema 版本等。
- `tenants`：租户（id/name/status）。

### 商品数据中心
| 表 | 说明 | 关键列 |
| --- | --- | --- |
| `products` | 商品主档 | tenant_id, id, name, category_id, brand, origin, description, status(draft/confirmed/verified/archived) |
| `categories` | 品类模板（CategorySchema 载体） | id, name, version, schema_json(attributes: key/label/type/unit/required/critical/allowed_values) |
| `category_versions` | 品类模板版本 | category_id, version, schema_json |
| `skus` | SKU 变体 | tenant_id, product_id, sku_code, attributes_json |
| `sources` | 原始资料（SourceFile） | tenant_id, product_id, name, mime, size, sha256, kind, purpose, view_angle, review_status |
| `imports` | 导入任务（ImportJob） | tenant_id, product_id, category, candidates(JSON), issues_json, blocks_json, status |
| `extraction_records` | AI 字段提取记录（ExtractionRecord） | tenant_id, import_job_id, source_file_id, raw_field, raw_value, mapped_field, extracted_value, confidence, source_location, model_name, prompt_version, extraction_status |
| `data_issues` | 数据异常（DataIssue） | tenant_id, product_id, attribute_key, issue_type, severity, source_records, resolution_status, resolution_value, resolved_by/at |
| `product_versions` | 商品不可变版本（ProductVersion） | tenant_id, product_id, version, fields(JSON), provenance_json, note, created_by |
| `batch_jobs` | 批量导入任务 | status, results_json |

### AI 内容策划中心
| 表 | 说明 | 关键列 |
| --- | --- | --- |
| `plans` | 策划任务（PlanningTask） | tenant_id, product_id, version_id, current_version_id, scene, channel, audience, content_type, content_json, status, blocked_json |
| `planning_versions` | 策划不可变版本（PlanningVersion） | tenant_id, planning_task_id, version_number, strategy_json, creative_json, image_plan_json, video_plan_json, approval_status |
| `outputs` | 生成资产 | tenant_id, plan_id, kind, filename, status, provider, model, prompt, params_json |
| `reviews` | 人工审核记录（PlanningReview/AuditLog 雏形） | tenant_id, target_type, target_id, action, note, payload_json |
| `audit_logs` | 审计日志（AuditLog） | tenant_id, operator_id, entity_type, entity_id, action, before_value, after_value, reason |

### 系统工程
| 表 | 说明 |
| --- | --- |
| `workflow_runs` | 工作流任务级聚合 |
| `workflow_steps` | 工作流节点（input/output 快照、error、retry_count、起止时间） |
| `workflow_events` | 工作流事件（幂等键） |
| `ai_execution_logs` | AI 调用审计（provider/model/model_version/prompt_version/token/cost/duration/status/error/retry/idempotency_key） |
| `generation_attempts` | 生成尝试记录 |
| `reference_tags` | 旧版视角标注（保留不删，已迁移） |

## 索引
商品/来源/版本/策划/输出/运行/提取/异常/AI 日志/审计等关键外键列均已建索引（见 `db.py` SCHEMA 底部）。
