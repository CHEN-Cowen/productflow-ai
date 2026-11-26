"""最小模型探针：验证配置与真实调用，输出可供行动的错误类别。

用法：
    python -m backend.probe_models config
    python -m backend.probe_models llm
    python -m backend.probe_models image --reference path/to/reference.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .errors import ApiError
from .providers import image as image_provider
from .providers import llm as llm_provider


def probe_llm() -> None:
    result = llm_provider.generate_structured(
        'Extract product_id and name. Return JSON {"product_id":"...","name":"..."}.',
        {"text": "BP01 女士双肩包"},
    )
    if result.get("product_id") != "BP01" or result.get("name") != "女士双肩包":
        raise SystemExit(f"模型返回与测试输入不符：{json.dumps(result, ensure_ascii=False)}")
    print(json.dumps(result, ensure_ascii=False))


def probe_image(reference: Path) -> None:
    content = reference.read_bytes()
    mime, width, height = image_provider.inspect_image(content)
    results = image_provider.generate(
        "保留参考图商品外观，生成干净背景的竖版商品展示图。",
        [{"content": content, "mime": mime}],
        ratio="3:4",
        count=1,
    )
    output = config.data_dir() / "model-probes" / ("reference-result" + (".png" if results[0]["mime"] == "image/png" else ".jpg"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(results[0]["content"])
    print(json.dumps({"reference": f"{width}x{height}", "output": str(output),
                      "size": f"{results[0]['width']}x{results[0]['height']}",
                      "model": results[0]["model"], "request_id": results[0].get("request_id", "")},
                     ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="ProductFlow AI 模型探针")
    parser.add_argument("provider", choices=("config", "llm", "image"))
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.provider == "config":
        print(json.dumps(config.model_status(), ensure_ascii=False, indent=2))
        return
    if args.provider == "llm":
        probe_llm()
        return
    if not args.reference or not args.reference.is_file():
        parser.error("image 需要 --reference 指定存在的 PNG/JPEG 参考图")
    probe_image(args.reference)


if __name__ == "__main__":
    try:
        main()
    except ApiError as error:
        raise SystemExit(f"[{error.code}] {error.message}\n提示：{error.hint}") from None
