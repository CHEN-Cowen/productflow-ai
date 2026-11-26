# 统一工作流与状态管理

## 分层

- `workflow_runs`（任务级聚合）：task_id / workflow_type / status / error。
- `workflow_steps`（节点级）：name / status / input_snapshot / output_snapshot / error_code / error_message / retry_count / started_at / completed_at。
- `workflow_events`（事件流）：event_type / payload_json，含幂等键。

## 统一状态（任务级）

`pending / running / review / paused / completed / failed / cancelled`

业务子状态：

- 商品导入：uploaded → parsing → extracting → normalizing → quality_checking → pending_review → publishing → verified → failed
- 内容策划：configuring → understanding → selling_point_analysis → strategy_generation → creative_generation → production_planning → pending_review → approved → dispatched → failed

## 执行规则

1. 单节点失败不丢已有记录（`workflow_steps` 独立保存）。
2. 单节点重试（retry_count 递增，上限 `WORKFLOW_RETRY_EXCEEDED`）。
3. 支持暂停/恢复/取消（状态字段）。
4. 执行历史可查（`steps(run_id)` / `events(run_id)`）。

## 幂等（防重复扣费）

对会产生外部费用的 AI 调用，用 `workflow.acquire(run_id, step_name, idempotency_key)` 做闸：同一 run+step+key 只放行一次。重试不重复创建数据、不重复扣费。

## 可回答的问题

哪个节点失败？为什么失败？用了哪个模型（`ai_execution_logs`）？是否已产生费用（cost）？能否重试（retryable）？是否需要人工介入（requires_human_action）？
