# 商品数据中心（Data Hub）数据治理

## 治理原则

1. 原始数据永远保留，不被清洗结果覆盖（`sources` 只读）。
2. AI 提取结果是候选数据，不直接写正式主数据（写 `extraction_records` + `imports.candidates`）。
3. 关键属性可追溯来源（`provenance_json`：source_id/locator/quote/raw_value/standard_value/method/status）。
4. 标准化优先确定性规则（`rules.canonicalize`）。
5. 冲突明确识别，不让 AI 擅自选择（`rules.build_issues` → `data_issues`）。
6. 关键事实人工确认（`imports.confirm`）。
7. 变更产生版本快照（`product_versions`）。

## 工作流

```
文件接入(upload_source) → 文件解析(parsing) → AI 字段提取(extract)
→ 字段映射与标准化(rules.canonicalize) → 数据质量检查(build_issues)
→ 人工审核(confirm/reject/modify) → 发布入库(publish) → 版本快照
```

## 关键规则（`backend/services/rules.py`）

- **单位归一**：dimension → cm，weight → g（0.65kg → 650g；280mm → 28cm）。
- **字段类型**：text / number / dimension / weight / enum（枚举允许值校验）。
- **异常识别**：missing / invalid / conflict / duplicate / unverified（+ 任务书的 low_confidence / untraceable 预留）。
- **宣传词事实约束**：`check_claims` 拦截无依据/绝对化宣传词。

## 发布规则（`data_hub.publish`，事务内）

1. 合法商品身份（name 非空）。
2. 必填属性完整。
3. 已填写的关键属性已确认且可追溯。
4. 无未解决的高/严重数据异常。
5. 存在商品版本快照。
6. 全部通过才置 `status=verified`，并写 `audit_logs`。

任一规则不满足，抛 `publish_blocked`，不置 verified，事务回滚（不出现部分成功）。

## 人工审核

- `confirm`：校验必填/类型/未知字段 + 手工字段必须填依据（`manual_basis_required`）。
- `reject`：驳回需填原因。
- 确认/驳回/发布均写 `reviews` 或 `audit_logs`。

## 增量更新与内容影响分析

`catalog.version_diff` 支持版本差异；`catalog.impact`（`GET /api/v1/data/products/{id}/impact`）在版本变化时输出受影响策划及**字段级影响原因**（哪些卖点绑定已变更字段、哪些文案/视觉/分镜引用旧值），供下游内容资产复审。
