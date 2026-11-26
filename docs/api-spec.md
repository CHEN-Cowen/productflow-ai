# ProductFlow AI API 规范

- 前缀：`/api/v1`
- 协议：REST，JSON（Pydantic 校验请求/响应）
- 鉴权：无登录系统；租户由 `X-Tenant-Id` 请求头注入（缺省 `default`），跨租户访问返回 `TENANT_ACCESS_DENIED`
- 错误：统一信封（见 `error-handling.md`）
- 时间：ISO 8601 UTC
- OpenAPI：启动后访问 `/docs`（FastAPI 自动生成）

## 商品数据中心 `/api/v1/data`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/data/products` | 商品列表（分页/搜索/品类筛选预留） |
| GET | `/data/products/{id}` | 商品详情（含版本/来源/异常/完整性） |
| POST | `/data/products/{id}/publish` | 发布入库（六条规则 + 事务 + 版本快照 + 审计） |
| GET | `/data/products/{id}/versions` | 版本历史 |
| GET | `/data/products/{id}/impact` | 内容影响分析（字段级影响原因） |
| GET | `/data/products/{id}/issues` | 数据异常（`resolution_status` 筛选） |
| POST | `/data/issues/{issue_id}/resolve` | 解决数据异常 |
| GET | `/data/products/{id}/audit` | 商品审计日志 |

> 既有 `/products`、`/imports`、`/plans`、`/outputs` 接口继续可用（见 README），与 `/data`、`/planning` 并存。

## 内容策划中心 `/api/v1/planning`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/planning/tasks` | 策划任务列表（`product_id` 过滤或全部） |
| POST | `/planning/tasks` | 创建策划任务（商品须已确认版本 + 参考图已标注视角） |
| GET | `/planning/tasks/{id}` | 任务详情 |
| POST | `/planning/tasks/{id}/cancel` | 取消（未确认） |
| GET | `/planning/tasks/{id}/review` | 审核视图 |
| POST | `/planning/tasks/{id}/approve` | 确认（生成不可变策划版本） |
| POST | `/planning/tasks/{id}/modify` | 修改（保存回草稿） |
| GET | `/planning/tasks/{id}/versions` | 策划版本列表 |
| GET | `/planning/tasks/{id}/versions/{vid}` | 策划版本详情 |
| GET | `/planning/tasks/{id}/output` | 结构化策划输出（须已确认） |
| POST | `/planning/tasks/{id}/dispatch` | 下发生产（须已确认；不伪造生成） |

## 租户 `/api/v1/tenants`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/tenants` | 租户列表 |
| POST | `/tenants` | 创建租户（本地工具，后续接入真实鉴权时收紧） |

## 提取记录 `/api/v1`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/imports/{id}/extractions` | 导入任务的提取记录 |
| GET | `/products/{id}/issues` | 商品数据异常 |
| POST | `/issues/{id}/resolve` | 解决数据异常（兼容路径） |

## 统一分页/ID

- 列表接口返回 `{"items": [...], "total": n}`；游标分页预留。
- 商品/品类/租户 ID 大写字母数字（`PRODUCT_ID` 正则校验）；SKU 编码大写。
