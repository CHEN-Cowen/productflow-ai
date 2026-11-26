# ProductFlow AI 后端升级实施计划

> 基于 `docs/backend-audit.md`。按任务书十三节的阶段推进，逐阶段实现 + 测试 + 报告，不把“计划完成”当“开发完成”。

## 阶段 0：现有系统审计 ✅
- 产物：`backend-audit.md`、`architecture.md`、`database-current.md`、`implementation-plan.md`
- 验收：明确复用与改造范围（已输出）

## 阶段 1：后端基础设施
- 统一配置管理（`config.py` 增加租户上下文、分页参数）
- 统一错误码 `backend/error_codes.py` + 标准错误信封（`ApiError` 扩展 retryable/requires_human_action/details；`main.py` 处理器统一输出）
- 租户模型 `tenants` 表 + `services/tenants.py` + 私有表补 `tenant_id`（回填默认租户） + 全量查询租户过滤
- AI 调用审计 `services/ai_logs.py` + `ai_execution_logs` 表
- 统一工作流 `services/workflow.py`（`workflow_steps`/`workflow_events` + 幂等键）
- 数据库迁移（幂等）
- **验收**：服务正常启动，35 项既有测试不回归，新增错误码/租户/AI 日志单测通过

## 阶段 2：商品数据中心基础能力
- 复用 Product/SKU/Category/CategorySchema（已存在）
- `imports` 状态机细化（uploaded→parsing→extracting→normalizing→quality_checking→pending_review→publishing→verified）
- `ExtractionRecord` 独立化（`extraction_records` 表 + `services/extractions.py`）
- 字段映射与标准化服务（复用 `rules.py`，补“字段名称映射/单位转换/枚举标准化/复杂属性拆分”）
- 文件解析（复用 `parsing.py`）
- **验收**：BP01 多格式资料导入 → 结构化候选数据（含来源定位与 confidence）

## 阶段 3：数据质量与人工审核
- `DataIssue` 独立化（`data_issues` 表 + `services/issues.py`，支持 missing/conflict/duplicate/invalid/low_confidence/untraceable + severity + resolution）
- 数据质量检查（完整性/准确性/一致性/唯一性/合理性/可追溯性）
- 人工审核（`/api/v1/data/reviews` + confirm/reject/modify/resolve）
- 商品发布（`/api/v1/data/products/{id}/publish`，事务 + 6 条规则 + 版本快照）
- `ProductVersion`（复用 `product_versions`）+ `AuditLog`（扩展 `reviews`）
- **验收**：识别高度冲突/重量单位差异/材质缺失，人工审核后入库；发布事务一致

## 阶段 4：AI 内容策划中心
- `PlanningTask`（复用 `plans`，补 `current_version_id`）+ 状态机
- 商品理解 `ProductUnderstandingService`（读取已确认版本/SKU/关键属性/素材/品牌规范 → ProductContext）
- 卖点 `SellingPointService`（事实绑定已确认字段，区分 verified_fact/creative_interpretation/unverified_claim）
- 营销策略 `MarketingStrategyService`（渠道模板 douyin/xiaohongshu/taobao/generic + 兜底）
- 创意 `CreativePlanningService`（2-3 个方向）
- 图片方案 `ImagePlanningService`（事实→视觉约束）
- 视频方案 `VideoPlanningService`（分镜时间/顺序/时长校验）
- **验收**：基于已确认 BP01 生成完整结构化策划

## 阶段 5：人工确认与生产接口
- `PlanningVersion`（`planning_versions` 表 + 不可变快照）
- `PlanningReview`（独立审核记录）
- JSON Schema（Pydantic）校验
- 确认/版本管理/下发 `dispatch`（未批准不可下发）
- **验收**：确认后才能下发，策划数据可被下游读取

## 阶段 6：整体测试与回归
- 单元测试 + 集成测试（任务书场景 A–H）+ 异常测试 + 权限（租户）测试 + 回归测试
- API 文档（`api-spec.md`）+ 开发文档（`data-governance.md`/`content-planning.md`/`workflow.md`/`error-handling.md`/`deployment.md`/`database.md`）
- **验收**：P0 核心链路通过

## 集成测试场景（来自任务书 §12.2）
- A：BP01 上传→解析→提取→标准化→质检→确认→入库
- B：两份文件高度 28cm/30cm → 识别冲突，未确认禁止发布
- C：0.65kg → 650g，保留原始值 + 转换记录
- D：内里材质缺失 → 创建 missing，AI 不猜测
- E：确认商品 → 抖音春节策划 → 理解/卖点/策略/创意/分镜 → 确认后输出合法 JSON
- F：策划中商品版本变化 → 检测 stale，要求重确认
- G：AI 超时 → 可重试状态，不重复建任务、不丢节点记录
- H：跨租户访问 → 拒绝

## 兼容策略
- 旧路径 `/products/{id}/imports`、`/plans` 等保留并转发到新服务，旧错误形状 `{detail:...}` 保留读取兼容，确保 §12.3 回归不破坏。
