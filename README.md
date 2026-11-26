# ProductFlow AI

## 阶段一验收记录

- 已通过：BP01 草稿保存、刷新读回、原始资料上传与预览，以及 DeepSeek 结构化商品字段返回。
- 待补验收：火山方舟 Seedream 5.5 已收到带 BP01 参考图的联调请求，返回 `SetLimitExceed`，尚未生成图片。额度恢复后，用 BP01 参考图出一张图并核对商品外观，再验证项目的 Python 调用链路。该项纳入阶段二至五的联合验收。

## 阶段二至五联合验收

1. 从已保存的商品页上传带文字层的 PDF，可以一起选择多份资料进行提取。确认字段原文和页码可以追溯，缺失或冲突的字段需要人工填写。
2. 确认商品版本后上传并标记六视角参考图。选择参考图、填写场景并生成策划。编辑提示词和分镜、保存并刷新检查。
3. 用已保存策划生成商品图和约 12 秒竖屏视频，分别预览。驳回时记录原因，可从策划重新生成。通过后检查下载入口。
4. 从历史策划复用参考素材，填写新场景并保存新策划。创建服饰商品，验证其品类字段独立于箱包。发布新版商品档案后，确认旧版成品暂停交付。

启动后端前，在同一终端配置下方的模型环境变量。视频需要支持 libx264 和 drawtext 的 FFmpeg，可用 `FFMPEG_PATH` 指定程序。中文字幕可以用 `FFMPEG_FONT` 指定包含中文字形的 TTF 字体文件。

第一阶段支持创建 BP01 商品草稿、从 SQLite 读回草稿，以及上传和预览原始资料。支持 PDF、PNG 和 JPEG，单个文件最多 10 MB。

## 本地运行

在项目根目录打开两个终端。后端需要 Python 3.10+，前端需要 Node.js 22+。

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm install
npm run dev
```

打开 http://localhost:5173，保存 BP01 草稿并刷新页面，再上传 PDF 或图片。再次刷新后，可点文件名打开预览。数据库和原始文件默认保存在 `data/`。

## 模型验证

在运行命令的终端设置 `LLM_URL`、`LLM_MODEL`、`LLM_API_KEY`，以及 `IMAGE_URL`、`IMAGE_MODEL`、`IMAGE_API_KEY`。URL 使用各自的完整接口地址。密钥通过环境变量提供。

```powershell
python -m backend.probe_models llm
python -m backend.probe_models image --reference path/to/reference.png
```

文本探针要求接口支持 OpenAI 兼容的 Chat Completions JSON 模式。生图探针用于支持 `image` 数据 URL 输入和 `b64_json` 响应的生成接口。成功后会输出结构化商品字段，或将生图文件写到 `data/model-probes/`。请选择允许传给模型服务商的参考图。
