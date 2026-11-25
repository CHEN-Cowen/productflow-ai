# ProductFlow AI

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
