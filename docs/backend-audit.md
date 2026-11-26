# ProductFlow AI 后端架构审计报告

> 生成日期：2026-11-26
> 审计范围：`backend/`、`tests/`、`docs/`、`data/` 与运行配置
> 结论基调：本项目已是一个可运行、可测试的模块化单体 MVP（35 项 pytest 通过）。本次升级为**增量改造**，以现有架构为基础补齐“数据治理 + 内容策划”两个业务闭环所需的工程能力，不推倒重写。

---

## 1. 当前项目技术架构

- **后端**：Python 3.12 + FastAPI（`backend/main.py` 的 `create_app()` 工厂函数）
- **前端**：React 18 + TypeScript + Vite 6（`frontend/`，`/api` 代理到 8000）
- **数据库**：SQLite，**原生 `sqlite3` + 手写 SQL**（无 ORM）。`backend/db.py` 用 `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` + 回填实现**幂等迁移**，可重复执行不破坏既有数据
- **数据校验**：Pydantic 2.x（`backend/api.py` 请求模型、`planning.py` 的 `PlanContent` 结构化校验）
- **文件存储**：本地文件系统（`config.data_dir()` 下 `uploads/`、`generated/`、`references/`、`samples/`），路径由 `PRODUCTFLOW_DATA` 覆盖
- **模型适配**：`backend/providers/`（llm / image / video / errors），业务层不直接依赖具体厂商
- **视频**：FFmpeg 合成（`backend/video.py`）
- **架构分层**：API 层（`api.py`）→ 服务层（`services/`）→ 解析/规则（`parsing.py`、`rules.py`）→ 数据访问（`db.py`）→ 文件存储（`config.py`）

**注意**：现有项目**没有**用户登录/鉴权系统，也没有租户概念；所有接口直接可用，未做身份隔离。

## 2. 当前数据库结构

`backend/db.py` 中的 `SCHEMA` 定义了以下表：

| 表 | 用途 | 关键列 |
| --- | --- | --- |
| `meta` | schema 版本等元数据 | key/value |
| `products` | 商品主档 | id, name, category_id, brand, origin, description, status(draft/confirmed), created_at, updated_at |
| `categories` | 品类模板（即 CategorySchema 的载体） | id, name, version, schema_json, is_builtin |
| `category_versions` | 品类模板版本 | category_id, version, schema_json |
| `skus` | SKU 变体 | id, product_id, sku_code, attributes_json |
| `sources` | 原始资料（SourceFile） | id, product_id, sku_id, name, mime, size, sha256, kind, purpose, view_angle, review_status, status |
| `imports` | 导入任务（ImportJob） | id, product_id, category, category_id, candidates(JSON), issues_json(JSON), source_ids_json, blocks_json, warnings_json, status |
| `product_versions` | 商品不可变版本（ProductVersion） | id, product_id, import_id, category, version, fields(JSON), provenance_json, sku, note, created_by |
| `plans` | 内容策划（PlanningTask） | id, product_id, version_id, scene, source_ids, script, channel, audience, content_type, content_json, status, blocked_json, parent_plan_id, reused_outputs_json |
| `outputs` | 生成资产 | id, plan_id, kind, filename, status, mime, size, provider, model, prompt, params_json, error, attempt, source_output_id |
| `reviews` | 人工操作记录（AuditLog 的雏形） | id, target_type, target_id, action, note, payload_json, reviewer |
| `workflow_runs` | 工作流执行记录 | id, task_id, product_id, workflow_type, status, steps_json, error, error_code |
| `generation_attempts` | 生成尝试记录（AIExecutionLog 的雏形） | id, plan_id, kind, attempt, status, prompt, params_json, provider, model, error_code, error, request_id, output_id |
| `batch_jobs` | 批量导入任务 | id, status, results_json |
| `reference_tags` | 旧版视角标注（已迁移到 sources.view_angle，保留不删） | source_id, angle |

## 3. 当前业务模块及代码位置

| 模块 | 文件 | 职责 |
| --- | --- | --- |
| 入口/工厂 | `backend/main.py` | create_app、迁移、CORS、静态托管、异常处理 |
| 路由 | `backend/api.py` | `/api/v1` 全部 REST 接口，仅做校验与组装 |
| 配置 | `backend/config.py` | 数据目录、上传上限、LLM/Image/Video/FFmpeg/OCR 环境变量与状态 |
| 数据访问 | `backend/db.py` | 连接、schema、幂等迁移、回填、内置品类种子 |
| 错误 | `backend/errors.py` | `ApiError`（status/message/code/hint）与错误类别提示 |
| 品类模板 | `backend/templates.py` | BAG/APPAREL 内置模板，字段可配置（type/unit/required/critical/allowed_values） |
| 商品/素材 | `backend/services/catalog.py` | 商品、品类、SKU、原始资料上传/预览/视角/审核、版本、影响面 |
| 文件解析 | `backend/services/parsing.py` | PDF/XLSX/DOCX/图片 OCR 解析，带来源定位 |
| 数据导入 | `backend/services/imports.py` | 抽取候选、来源校验、规则、确认入库、批量导入 |
| 规则 | `backend/services/rules.py` | 单位归一、必填/类型校验、冲突/重复识别、宣传词事实校验 |
| 内容策划 | `backend/services/planning.py` | 策划生成/编辑/确认/复用、事实约束、结构化校验 |
| 内容生产 | `backend/services/generation.py` | 生图、视频、审核、交付、资产库、统计 |
| 工作流 | `backend/services/runs.py` | workflow_runs 记录（节点状态、错误、耗时） |
| 模型适配 | `backend/providers/llm.py` `image.py` `video.py` `errors.py` | 文本 JSON 模式、火山方舟生图、Seedance 视频、错误分类 |
| 视频 | `backend/video.py` | FFmpeg 合成与 ffprobe 校验 |
| 演示数据 | `backend/seed_demo.py` | BP01 主线 + AP01 第二品类样例 |

## 4. 可以直接复用的模块

1. **品类属性模板（CategorySchema）**：`templates.py` + `categories.schema_json` + `category_versions`，已支持 `required/critical/type/unit/allowed_values`，等价于任务书的 CategorySchema，无需重做。
2. **商品/版本/SKU**：`products` / `product_versions`（不可变版本快照）/ `skus`，已满足“商品 ID 稳定、版本递增、SKU 与 SPU 分离”。
3. **原始资料 SourceFile**：`sources` 表 + `catalog.upload_source` 已实现：内容识别文件类型（不信任扩展名）、SHA256 去重、大小校验、只读保存、商品归属校验、预览完整性校验。
4. **文件解析**：`parsing.py` 已实现 PDF/XLSX/DOCX/OCR 解析与来源定位（页码/工作表行列/段落/表格行列），失败降级保留原件。
5. **数据标准化与质量规则**：`rules.py` 的 `canonicalize`（单位归一：0.65kg→650g、cm/mm/m 统一）、`build_issues`（missing/invalid/conflict/duplicate）、`validate_fields`、`check_claims`（宣传词事实约束）。
6. **模型适配层**：`providers/` 已实现 LLM/Image/Video 三类 Provider，含 JSON 模式、错误分类、超时与连接处理，业务层不直接调厂商 API。
7. **工作流运行记录**：`workflow_runs` + `runs.py`，已有节点状态与耗时记录。
8. **人工操作记录**：`reviews` 表已记录 import/plan/output 的 confirm/reject/edit 等动作，可作为 AuditLog 扩展基础。
9. **内容策划事实约束**：`planning.py` 已强制卖点绑定已确认字段与原文依据，`check_claims` 拦截无依据/绝对化宣传词。
10. **文件存储**：`config.py` 的本地目录 + `generation`/`catalog` 已处理路径安全与完整性校验。

## 5. 需要修改的模块

| 模块 | 需要的修改 |
| --- | --- |
| `errors.py` | 引入统一 `ErrorCode` 枚举与标准错误信封 `{success, error:{code,message,details,retryable,requires_human_action}}`（当前是 `{detail:{code,message,hint}}`） |
| `db.py` | 新增 `tenants` 表，并给 `products/sources/imports/product_versions/plans/outputs` 等私有数据表补 `tenant_id` 列（回填默认租户）；新增 `ai_execution_logs`、`workflow_steps`/`workflow_events`、`planning_versions` 等表 |
| `api.py` | 新增 `/api/v1/data/*`（Data Hub）与 `/api/v1/planning/*`（Content Planning）命名空间路由；统一分页/错误格式/租户隔离；错误响应改为标准信封 |
| `services/imports.py` | 导入任务状态机细化为 `uploaded→parsing→extracting→normalizing→quality_checking→pending_review→publishing→verified`；抽取记录独立化 |
| `services/catalog.py` | 商品状态从 `draft/confirmed` 迁移为 `draft/pending_review/verified/archived`；发布走事务 |
| `services/planning.py` | 策划增加不可变 `PlanningVersion`；拆分为商品理解/卖点/策略/创意/图片/视频方案服务；增加下发接口 |
| `services/runs.py` | 细化 step 为独立 `workflow_steps`，支持幂等键、重试、暂停/恢复/取消；补 AI 调用计费记录 |
| `services/generation.py` | 生图/视频调用落 `ai_execution_logs`（provider/model/version/token/cost/duration/status/retry） |
| `config.py` | 增加租户解析、默认租户、分页参数等 |

## 6. 需要新增的模块

1. **Tenant 模型与服务**（`services/tenants.py`）：租户表 + 所有私有数据强制 `tenant_id` 过滤 + 跨租户访问拒绝（`TENANT_ACCESS_DENIED`）。
2. **统一 ErrorCode**（`backend/error_codes.py`）：任务书列出的 `FILE_FORMAT_UNSUPPORTED` / `DATA_CONFLICT` / `PRODUCT_NOT_VERIFIED` / `WORKFLOW_RETRY_EXCEEDED` / `TENANT_ACCESS_DENIED` 等。
3. **AIExecutionLog 服务**（`services/ai_logs.py`）：模型调用统一记录 provider/model/model_version/prompt_version/input摘要/output摘要/token/cost/duration/status/error/retry_count。
4. **DataIssue 独立服务**（`services/issues.py`）：将当前 `imports.issues_json` 内联 JSON 独立为可查询、可解决、带严重程度的 `data_issues` 表。
5. **ExtractionRecord 独立服务**：将 `imports.candidates` 内联 JSON 独立为 `extraction_records` 表（含 confidence/model_name/prompt_version/extraction_status）。
6. **PlanningVersion/PlanningReview 服务**：策划不可变版本 + 独立审核记录。
7. **结构化策划输出服务**（`PlanningOutputService`）：输出统一 JSON，经 Pydantic Schema 校验；`dispatch` 下发接口（未批准不可下发）。
8. **统一工作流编排**（`services/workflow.py`）：`WorkflowRun/WorkflowStep/WorkflowEvent`，支持单节点失败/重试/暂停/恢复/取消，AI 调用幂等键防重复扣费。

## 7. 现有架构存在的问题

1. **无租户隔离**：`products/sources/imports/plans/outputs` 均无 `tenant_id`，无法满足“不同租户不能互访”的硬性要求（任务书 §11 第 1、2 条）。
2. **关键数据模型内联 JSON**：`imports.candidates`（抽取记录）、`imports.issues_json`（数据异常）内联在单表 JSON 字段里，无法按字段/严重程度/来源独立查询、索引与追溯，也不符合 `DataIssue`/`ExtractionRecord` 的独立建模要求。
3. **策划无版本**：`plans` 表可被 `update_plan` 原地覆盖，无 `PlanningVersion` 不可变快照，无法满足“确认后创建不可直接覆盖的策划版本”。
4. **商品状态粒度不足**：商品只有 `draft/confirmed`，缺少 `pending_review/verified/archived` 与“发布必须事务 + 满足全部规则才置 verified”的显式状态机。
5. **错误格式与 ErrorCode 不统一**：错误信封是 `{detail:{code,message,hint}}`，缺少 `success/retryable/requires_human_action` 与任务书约定的错误码集合；`code` 散落各处、口径不一致。
6. **AI 调用无统一计费/审计日志**：`providers` 只记耗时到日志文件，`generation_attempts` 无 token/cost/model_version/prompt_version，无法回答“哪个模型、是否已产生费用、能否重试”。
7. **工作流步骤粒度粗**：`workflow_runs.steps_json` 为内联数组，无独立 `workflow_steps` 表，缺少幂等键、暂停/恢复/取消与 `input_snapshot/output_snapshot`。
8. **API 命名空间与任务书不一致**：现有接口散落在 `/products/{id}/imports`、`/plans` 等，任务书要求 `/api/v1/data/*`、`/api/v1/planning/*`、`/api/v1/data/reviews` 等规范化命名。
9. **无统一分页与统一 ID 规范**：列表接口多数一次性返回全部，未统一分页与游标。
10. **发布非严格事务语义**：`confirm` 中版本插入 + 状态更新 + review 记录在同一 `session()` 事务内（已基本满足），但“发布规则 6 条全部校验 + 快照 + 状态”需要显式收敛到统一发布服务。

## 8. 本次改造方案

以**模块化单体**、**现有原生 SQLite + 手写 SQL + Pydantic** 为基础，采用以下原则适配任务书（§2.3：与任务书技术选型不一致时以现有架构为准，不重写）：

1. **数据访问层保持原生 SQL**，不引入 SQLAlchemy/Alembic；迁移沿用 `db.py` 的幂等 `CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN + 回填` 模式（数据库设计预留 PostgreSQL 迁移空间：避免 SQLite 特有函数进业务逻辑）。
2. **新增租户维度**：`tenants` 表 + 私有表补 `tenant_id`（回填默认租户 `default`），所有业务查询强制 `tenant_id` 过滤，跨租户拒绝。无现有鉴权系统，先以“默认单租户 + 可注入的租户上下文”实现，不破坏现有接口默认行为。
3. **统一错误信封与 ErrorCode**：新增 `backend/error_codes.py`，`ApiError` 扩展 `retryable/requires_human_action/details`，`main.py` 异常处理器统一输出 `{success,error:{code,message,details,retryable,requires_human_action}}`；保留对旧 `{detail:...}` 形状的兼容（现有前端/测试不破坏）。
4. **关键模型独立化**：`data_issues`、`extraction_records`、`planning_versions` 独立建表，`imports.candidates/issues_json` 逐步迁移到新表（保留旧列读取兼容）。
5. **策划不可变版本**：`planning_versions` 表保存每次确认快照，`plans.current_version_id` 指向最新版本。
6. **AI 执行日志**：`ai_execution_logs` 表统一记录模型调用（provider/model/model_version/prompt_version/input摘要/output摘要/token/cost/duration/status/error/retry_count/idempotency_key）。
7. **统一工作流**：`workflow_steps`/`workflow_events` 独立表，`workflow_runs` 保留任务级聚合；AI 调用用 `task_id + step_name + idempotency_key` 防重复。
8. **新命名空间路由**：新增 `/api/v1/data/*` 与 `/api/v1/planning/*` 作为标准接口，同时保留现有 `/products/{id}/imports`、`/plans` 等旧路径做兼容转发（§12.3 回归不破坏）。

## 9. 预计涉及的文件和数据库迁移

### 新增文件
- `backend/error_codes.py`（统一 ErrorCode 枚举与错误信封构造）
- `backend/services/tenants.py`（租户服务）
- `backend/services/ai_logs.py`（AI 执行日志服务）
- `backend/services/issues.py`（DataIssue 服务）
- `backend/services/extractions.py`（ExtractionRecord 服务）
- `backend/services/workflow.py`（统一工作流编排，扩展 runs.py）
- `backend/services/data_hub.py`（Data Hub 聚合服务：导入/解析/提取/标准化/质量/审核/发布）
- `backend/services/content_planning.py`（Content Planning 聚合服务：商品理解/卖点/策略/创意/图片/视频方案/版本/下发）
- `backend/api/data.py`、`backend/api/planning.py`（新命名空间路由）
- `tests/test_data_hub.py`、`tests/test_planning_center.py`、`tests/test_tenants.py`、`tests/test_ai_logs.py` 等

### 数据库迁移（幂等，不破坏现有数据）
1. 新增 `tenants` 表，种子默认租户。
2. `products/sources/imports/product_versions/plans/outputs/reviews/workflow_runs` 补 `tenant_id`（默认回填 `default`）。
3. 新增 `data_issues`、`extraction_records`、`ai_execution_logs`、`workflow_steps`、`workflow_events`、`planning_versions` 表。
4. `products.status` 语义迁移：旧 `confirmed` → 新 `verified`（回填），新增 `pending_review/archived`。

### 文档
- `docs/architecture.md`、`docs/database.md`、`docs/api-spec.md`、`docs/data-governance.md`、`docs/content-planning.md`、`docs/workflow.md`、`docs/error-handling.md`、`docs/deployment.md`

---

## 结论

现有项目已具备 Data Hub 与 Content Planning 的**业务骨架**（模板、版本、解析、规则、策划、生产、审核），缺的是**企业级工程能力**：租户隔离、统一错误码、AI 调用审计、关键模型独立化、策划版本化、统一工作流。本次按上述方案增量补齐，逐阶段测试验收，不破坏既有 35 项测试与前端契约。
