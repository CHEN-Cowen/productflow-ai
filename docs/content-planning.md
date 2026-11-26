# AI 内容策划中心（Content Planning）

## 定位

以可信商品数据为基础，产出**经确认、可下发**的结构化内容策划方案；不直接生成图片/视频，而是生成交给下游生产模块执行的方案。

## 事实约束

- 只依据已确认商品版本与参考素材策划（`planning.create_plan` 要求 `version_required`）。
- 卖点必须绑定已确认字段与原文依据（`SellingPoint.field/evidence`）。
- 无依据/绝对化宣传词被拦截（`rules.check_claims` → `blocked` → `claim_blocked`）。
- 参考图必须属于该商品、已标注视角、非废弃状态。

## 工作流与状态

```
创建任务(draft) → 商品理解/卖点/策略/创意/图片/视频方案(模型生成)
→ 人工审核(approve/modify/cancel) → 策划版本快照(approved)
→ 结构化输出(output) → 下发生产(dispatch)
```

## 数据结构

- `plans`（PlanningTask）：任务主档，`current_version_id` 指向最新策划版本。
- `planning_versions`（PlanningVersion）：每次确认的不可变快照，拆为 strategy_json / creative_json / image_plan_json / video_plan_json。
- `reviews`（PlanningReview）：确认/驳回/修改/下发记录。

## 结构化输出（§7.9）

`GET /api/v1/planning/tasks/{id}/output` 返回：

```json
{
  "planning_task_id": "...",
  "schema_version": "1.0",
  "product_id": "...",
  "product_version_id": 1,
  "channel": "抖音",
  "marketing_goal": "抖音春节年货节",
  "target_audience": "约30岁女性",
  "selling_points": [],
  "marketing_strategy": {},
  "creative_brief": {},
  "image_plan": {},
  "video_plan": {},
  "reference_asset_ids": [],
  "approval_status": "approved"
}
```

## 下发（dispatch）

`POST /api/v1/planning/tasks/{id}/dispatch`：仅在策划已确认（approved）后允许，返回结构化方案并记录下发事件；**不伪造图片/视频已生成**（真实生产由下游模块执行）。

## 渠道策略模板

`backend/services/channel_strategy.py` 提供 `douyin / xiaohongshu / taobao / generic` 差异化策略（content_positioning / expression_strategy / CTA / video_constraints）。策划时注入模型上下文，确认后写入 `planning_versions.strategy_json.channel_strategy`。支持中英文别名（抖音/小红书/淘宝），无专属模板回退通用模板，不因缺模板使策划失败。
