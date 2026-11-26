# ProductFlow AI

面向商品运营、内容运营与审核人员的商品数据治理与 AI 内容生产系统。把分散的原始资料加工成**可追溯、可审核、可复用**的商品档案，并基于已确认版本和参考图生产营销主图与短视频。

技术栈：React 18 + TypeScript + Vite 6 前端，FastAPI + SQLite + 本地文件存储后端，模块化单体，REST 前缀 `/api/v1`。视频用 FFmpeg 合成，图片/文本走可配置的模型适配层。

三个核心对象各自独立建模、独立生命周期，并互相引用：

| 对象 | 表 | 生命周期 |
| --- | --- | --- |
| 商品事实 | `products` / `product_versions` / `skus` | 草稿 → 候选提取 → 规则校验 → 人工确认（不可变版本）→ 变更产生新版本 |
| 原始输入素材 | `sources` | 上传 → 解析定位 → 视角/用途标注 → 审核状态 |
| 生成输出资产 | `outputs` / `reviews` | 生成 → 待审核 → 通过（可下载）/ 驳回（暂留队列）→ 修订 |

## 目录结构

```
backend/
  main.py          # create_app：配置、迁移、CORS、静态托管、错误处理
  api.py           # /api/v1 路由
  config.py        # 环境变量、数据目录、上传上限、模型/FFmpeg/OCR 状态
  db.py            # SQLite schema、幂等迁移、回填、内置品类模板
  errors.py        # ApiError 与错误类别/可执行提示
  templates.py     # 箱包 / 服饰品类模板
  providers/       # llm.py（JSON 模式）、image.py（方舟生图）、errors.py（错误分类）
  services/
    catalog.py     # 商品、版本、SKU、资料上传/预览/视角、影响面
    parsing.py     # PDF / Excel / Word / 图片 OCR 解析与定位
    imports.py     # 抽取候选、来源校验、规则、确认入库、批量导入
    planning.py    # 策划生成/编辑/确认/复用、事实约束
    generation.py  # 生图、视频、审核、交付、资产库、统计
    runs.py        # 工作流运行记录
    rules.py       # 单位归一、必填/冲突/重复、宣传词校验
  video.py         # FFmpeg 合成与 ffprobe 校验
  probe_models.py  # 模型最小探针
  seed_demo.py     # 演示数据（BP01 主线 + AP01 第二品类）
frontend/
  main.tsx         # hash 路由入口
  api.ts           # REST 客户端
  pages/           # 工作台、商品、商品详情（7 个 tab）、批量导入、审核、资产库、工作室
tests/             # pytest：33 项
```

## 数据目录与迁移

- 数据（SQLite、上传原件、生成成品、样例）默认在 `data/`，由 `PRODUCTFLOW_DATA` 覆盖，已被 `.gitignore` 忽略。
- 启动时执行 `init_db()`：`CREATE TABLE IF NOT EXISTS` + 按需 `ALTER TABLE ADD COLUMN` + 回填，可重复执行、不破坏既有草稿/资料/版本/成品。
- 旧数据兼容：旧 `reference_tags` 表迁移为资料视角；历史资料缺失的文件大小从磁盘回填；旧输出保留并标注。

## 环境变量

复制 `.env.example` 为 `.env`（已被忽略）。后端启动时自动读取 `.env`，但不覆盖已存在的环境变量。

| 变量 | 用途 |
| --- | --- |
| `LLM_URL` / `LLM_MODEL` / `LLM_API_KEY` | 文本模型，兼容 DeepSeek Chat Completions JSON 模式 |
| `LLM_TIMEOUT` | 文本请求超时秒数，默认 120 |
| `IMAGE_URL` / `IMAGE_MODEL` / `IMAGE_API_KEY` | 生图，默认火山方舟 `/api/v3/images/generations`，模型填控制台可用 Seedream ID 或接入点 |
| `IMAGE_SIZE` / `IMAGE_TIMEOUT` / `IMAGE_DOWNLOAD_TIMEOUT` | 生图尺寸（默认 `1024x1365`）与超时 |
| `FFMPEG_PATH` / `FFPROBE_PATH` / `FFMPEG_FONT` | 视频合成程序与中文字体，默认从 PATH 查找并自动选择微软雅黑/黑体 |
| `TESSERACT_CMD` | 图片 OCR，未安装时降级为“保留原件 + 人工补充” |
| `PRODUCTFLOW_DATA` | 本地数据目录，默认 `./data` |

密钥只在后端读取；接口与日志不返回密钥、完整 Base64 或签名 URL。`/api/v1/models/status` 只检查配置是否存在。

## Windows 本地启动

后端需要 Python 3.10+，前端 Node.js 22+。仓库不提交 `.venv` 与 `node_modules`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm install
npm run dev
```

打开 http://localhost:5173 。Vite 已把 `/api` 代理到 8000。生产预览可用 `npm run build` 后用后端直接托管（存在 `dist/` 时后端以 `StaticFiles(html=True)` 挂载根路径）。

## 演示数据

```powershell
# 六视角参考图 + 样例规格表 + BP01 样例版本 + 春节/日常两条策划 + AP01 第二品类 + 真实合成视频
.\.venv\Scripts\python.exe -m backend.seed_demo

# 只准备数据，不合成视频
.\.venv\Scripts\python.exe -m backend.seed_demo --no-video

# 已配置生图模型时，额外生成一张真实商品图
.\.venv\Scripts\python.exe -m backend.seed_demo --image
```

说明：

- 六视角图来自工作区的 `BP01六张高清图.zip`，复制进 `data/references` 后作为 BP01 资料入库（不提交）。
- 样例规格表 `BP01-样例规格.xlsx` 是**按复试题字段生成的样例**，不是供应商原件；版本 `note`、来源和商品描述都标注“样例、非供应商原件”。
- `AP01` 为服饰第二品类，含多 SKU，用于验证同一实体模型支持不同字段模板。
- 脚本幂等，可重复运行。

演示主线：BP01 原始资料 → AI 抽取/人工录入 → 规则检查 → 人工确认 → 六视角素材 → 春节场景策划 → 真实主图（需额度）与视频 → 审核下载 → 历史素材复用（日常商品展示）。

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查（含数据库与模型配置状态） |
| GET | `/api/v1/models/status` | 模型/FFmpeg/OCR 可用性与阻塞提示 |
| GET/POST | `/api/v1/categories` | 品类模板列表 / 新增 |
| PUT | `/api/v1/categories/{id}` | 编辑模板（保留模板版本） |
| GET/POST | `/api/v1/products` | 商品列表 / 创建草稿（重复编号返回 `duplicate_product`） |
| GET/PUT | `/api/v1/products/{id}` | 商品详情 / 更新 |
| GET | `/api/v1/products/{id}/versions` | 版本历史 |
| GET | `/api/v1/products/{id}/versions/diff` | 版本差异 |
| GET | `/api/v1/products/{id}/impact` | 受影响成品（待复审/暂停交付） |
| GET/POST | `/api/v1/products/{id}/skus` | SKU 列表 / 新增 |
| POST | `/api/v1/products/{id}/sources` | 上传原始资料（类型/体积校验、哈希去重） |
| GET | `/api/v1/products/{id}/sources/{sid}` | 原件预览（校验商品归属） |
| PUT | `/api/v1/products/{id}/sources/{sid}` | 更新视角/用途/审核状态/SKU 关联 |
| POST | `/api/v1/products/{id}/sources/{sid}/suggest-angle` | AI/规则建议视角 |
| POST | `/api/v1/products/{id}/imports/extract` | 解析并抽取候选（`manual=true` 不调用模型） |
| GET | `/api/v1/imports/{id}` | 导入详情（候选/异常/原文定位/警告） |
| POST | `/api/v1/imports/{id}/confirm` | 人工确认入库，生成不可变版本 |
| POST | `/api/v1/imports/{id}/reject` | 驳回导入 |
| POST | `/api/v1/imports/batch` | 跨商品批量导入，逐条结果 |
| GET | `/api/v1/assets/sources` | 素材库（按商品/视角/审核状态/关键词筛选） |
| GET | `/api/v1/library/outputs` | 资产库（按状态/类型/商品筛选） |
| GET/POST | `/api/v1/products/{id}/plans` | 策划列表 / 创建（读取已确认版本与参考图） |
| GET/PUT | `/api/v1/plans/{id}` | 策划详情 / 编辑（保存后回到草稿待确认） |
| POST | `/api/v1/plans/{id}/confirm` | 确认策划（无依据宣传词返回 `claim_blocked`） |
| POST | `/api/v1/plans/{id}/reuse` | 用历史已审核资产创建新场景 |
| POST | `/api/v1/plans/{id}/outputs/image` | 生图（真实 API） |
| POST | `/api/v1/plans/{id}/outputs/video` | FFmpeg 合成视频（10–15s、9:16） |
| GET | `/api/v1/products/{id}/outputs` | 商品成品列表 |
| GET | `/api/v1/outputs/{id}` | 成品预览 |
| GET | `/api/v1/outputs/{id}/download` | 下载（仅通过审核且非过期） |
| PUT | `/api/v1/outputs/{id}/review` | 通过 / 驳回（驳回必须填原因） |
| POST | `/api/v1/outputs/{id}/revise` | 创建修订任务 |
| GET | `/api/v1/products/{id}/workflow` | 商品工作流聚合 |
| GET | `/api/v1/stats` | 真实指标（含定义/分母/样本量，缺数据显式未采集） |

错误统一返回 `{ "error": { "code", "message", "hint" } }`，类别含 `provider_not_configured`、`provider_auth`、`provider_permission`、`provider_quota`、`provider_timeout`、`provider_connection`、`provider_invalid_json`、`provider_format`、`provider_download`、`ffmpeg_error`、`ffmpeg_missing`、`stale_version`、`stale_output`、`claim_blocked`、`manual_basis_required`、`duplicate_product`、`duplicate_source`、`unsupported_file` 等。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q     # 后端 33 项
npm run build                                      # tsc --noEmit + vite build
```

覆盖：模型错误分类与 JSON 重试、草稿读回、重复编号、非法文件拦截、PDF/Excel/Word 解析与来源定位、旧版无扩展名资料迁移后可预览、等价单位、来源冲突、重复值、手动更正与依据、第二品类/SKU、批量导入逐条结果、素材视角持久化、策划事实约束与“纯羊毛/防水”拦截、策划编辑读回、生图（mock）、审核驳回到通过、下载权限、修订、视频真实 FFmpeg 合成与 ffprobe 校验（时长/画幅/编码）、版本变更定位受影响成品。

## 已实现 / 已测试 / 真实接口通过 / 待确认

**已实现**：五阶段全部功能与页面入口；SQLite 幂等迁移；模型适配层与错误分类；PDF/Excel/Word/OCR 解析；候选来源定位校验；规则与版本；六视角素材；事实约束策划；FFmpeg 视频；审核交付；资产复用；批量导入；统计。

**已测试**：上述 33 项 pytest；`npm run build`；浏览器验收商品详情、素材、策划、视频预览、审核通过与下载。

**真实接口通过**：FFmpeg 真实合成 11.4s、720×1280、H.264、yuv420p 视频并经 ffprobe 与浏览器验证；真实文件解析（手写文字层 PDF/Excel/Word/PNG）。

**仍待确认**：
- 火山方舟 Seedream 真实生图仍未成功（历史报 `SetLimitExceed`，额度问题），页面与任务记录会显示 `provider_quota` 提示；额度恢复后用 `backend.seed_demo --image` 或界面生成验证。
- 真实 DeepSeek/方舟密钥未在本次环境提供，真实文本/生图调用未跑通；模拟结果与真实结果分开记录。
- 原始 BP01 供应商资料未在工作区提供，当前以样例规格表和样例版本演示，未冒充已核验事实。
- 未推送远端：本地提交已完成，推送需要仓库写权限。

## 与 PRD 的差异

- PRD 提到 Tailwind/shadcn 与 PostgreSQL/对象存储：当前为纯 CSS 与 SQLite + 本地文件，属本地业务闭环优先；PostgreSQL、对象存储、ERP 同步、复杂权限、分布式队列列为后续演进。
- 原始 BP01 资料与参考图只在工作区使用，未提交仓库。
