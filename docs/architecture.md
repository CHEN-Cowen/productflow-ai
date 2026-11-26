# ProductFlow AI 目标架构

> 模块化单体。以现有 FastAPI + 原生 SQLite + Pydantic 为基础增量演进，为后续迁移 PostgreSQL / 对象存储预留空间。

## 1. 分层

```
frontend (React 18 + Vite)            # 不修改，仅消费后端契约
        │  /api/v1 (REST + JSON Schema)
        ▼
┌─────────────────────────────────────────────┐
│ API 接口层  api.py / api/data.py / api/planning.py │ 参数校验、租户上下文、分页、错误信封
├─────────────────────────────────────────────┤
│ 业务服务层  services/                         │ catalog / imports / issues /
│           data_hub / content_planning / ...  │ extraction / planning / generation
├─────────────────────────────────────────────┤
│ 工作流编排层 services/workflow.py             │ WorkflowRun / WorkflowStep / WorkflowEvent
├─────────────────────────────────────────────┤
│ AI 模型适配层 providers/                      │ LLM / Vision / Image / Video (预留)
│           + services/ai_logs.py             │ 统一调用审计（token/cost/duration/retry）
├─────────────────────────────────────────────┤
│ 数据访问层 db.py（原生 SQL + 幂等迁移）        │ tenant_id 隔离、版本快照、软删除策略
├─────────────────────────────────────────────┤
│ 文件与资产存储层 config.py（本地 FS，预留对象存储接口）│ uploads / generated / references / samples
└─────────────────────────────────────────────┘
```

## 2. 核心设计约束

1. **租户隔离**：所有私有数据（products/sources/imports/versions/plans/outputs/reviews/issues/extractions/ai_logs/workflow_runs）带 `tenant_id`；服务层每个查询都强制 `tenant_id` 过滤，跨租户访问抛 `TENANT_ACCESS_DENIED`。
2. **原始数据不可覆盖**：上传原件只读；AI 提取结果只写 `extraction_records`（候选），不直接写 `product_versions`；正式数据变更只产生新版本快照。
3. **模型调用统一审计**：所有 LLM/Vision/Image/Video 调用经 `services/ai_logs.py` 落 `ai_execution_logs`，业务层禁止绕过。
4. **统一错误信封**：所有错误返回 `{success:false, error:{code,message,details,retryable,requires_human_action}}`。
5. **幂等与有限重试**：外部计费调用使用 `task_id + step_name + idempotency_key` 防重复；重试上限 `WORKFLOW_RETRY_EXCEEDED`。
6. **版本不可变**：商品版本、策划版本、品类模板版本均追加式，普通更新接口不能覆盖已确认快照。
7. **不破坏现有契约**：保留旧路径与旧错误形状的兼容读取，新能力以新命名空间 `/api/v1/data/*`、`/api/v1/planning/*` 提供。

## 3. 业务闭环

```
多源商品资料接入 → 文件解析 → AI 字段提取 → 字段映射与标准化
→ 数据质量检查 → 人工审核 → 商品主数据入库(版本化)
→ 商品理解 → 卖点分析 → 营销策略生成 → 创意策划
→ 图片/视频生产方案 → 人工确认 → 结构化策划结果下发
```

## 4. 演进预留

- SQLite → PostgreSQL：数据访问收敛在 `db.py`，业务层不写 SQLite 特有函数（`json` 序列化统一 `dumps/loads`）。
- 本地文件 → 对象存储：存储路径与签名 URL 由 `config.py`/存储服务统一出口，业务层不直接拼路径。
- 单租户 → 多租户：`tenants` + 可注入租户上下文，接入真实登录/鉴权时替换上下文来源即可，不改业务 SQL。
