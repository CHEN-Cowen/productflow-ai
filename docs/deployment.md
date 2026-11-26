# 部署与运行

## 环境要求

- Python 3.10+（本仓库用 3.12）
- Node.js 22+（前端，仅本地开发/构建需要）
- FFmpeg/ffprobe（视频合成，可选，默认从 PATH 查找）
- tesseract（图片 OCR，可选，未装则降级为人工补充）

## 环境变量

复制 `.env.example` 为 `.env`（已 git 忽略）。关键项：

| 变量 | 用途 |
| --- | --- |
| `LLM_URL/LLM_MODEL/LLM_API_KEY` | 文本模型（DeepSeek Chat Completions 兼容，JSON 模式） |
| `IMAGE_URL/IMAGE_MODEL/IMAGE_API_KEY` | 生图（火山方舟 Seedream） |
| `VIDEO_URL/VIDEO_MODEL/VIDEO_API_KEY` | 视频（火山方舟 Seedance，异步任务式） |
| `FFMPEG_PATH/FFPROBE_PATH/FFMPEG_FONT` | 视频合成程序与中文字体 |
| `TESSERACT_CMD` | OCR 引擎 |
| `PRODUCTFLOW_DATA` | 本地数据目录，默认 `./data` |

密钥只在后端读取，不写入代码/数据库明文/Git，接口与日志不返回密钥。

## 后端启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

启动时自动执行幂等迁移（建表 + 补列 + 回填 + 种子内置品类与默认租户）。

## 前端（可选）

```powershell
npm install
npm run dev        # http://localhost:5173，/api 代理到 8000
npm run build      # tsc --noEmit + vite build；存在 dist/ 时后端直接托管
```

## 演示数据

```powershell
.\.venv\Scripts\python.exe -m backend.seed_demo --no-video
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 部署说明

- 本地模块化单体，未引入微服务/分布式组件。
- 数据（SQLite + 上传原件 + 生成成品）默认在 `data/`，`PRODUCTFLOW_DATA` 覆盖。
- 数据库设计预留 PostgreSQL 迁移；文件存储预留对象存储接口。
- 真实模型 API 未配置时，接口返回 `AI_PROVIDER_UNAVAILABLE` 等可行动错误，Mock 结果与真实结果分开标记，不冒充真实生产。
