import argparse
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post(prefix, payload):
    config = {key: os.getenv(f"{prefix}_{key}") for key in ("URL", "API_KEY", "MODEL")}
    missing = [f"{prefix}_{key}" for key, value in config.items() if not value]
    if missing:
        raise SystemExit("尚未配置 " + ", ".join(missing))
    request = Request(
        config["URL"], data=json.dumps({"model": config["MODEL"], **payload}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {config['API_KEY']}"},
    )
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description="验证 ProductFlow AI 模型连接")
    parser.add_argument("provider", choices=("llm", "image"))
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.provider == "llm":
        result = post("LLM", {
            "messages": [
                {"role": "system", "content": "Extract product_id and name as a JSON object."},
                {"role": "user", "content": "BP01 女士双肩包"},
            ],
            "response_format": {"type": "json_object"},
        })
        fields = json.loads(result["choices"][0]["message"]["content"])
        if fields != {"product_id": "BP01", "name": "女士双肩包"}:
            raise ValueError("模型返回的字段与测试输入不符")
        print(json.dumps(fields, ensure_ascii=False))
        return

    if not args.reference or args.reference.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        parser.error("image 需要 --reference 指定 PNG 或 JPEG 参考图")
    mime = "image/png" if args.reference.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(args.reference.read_bytes()).decode("ascii")
    result = post("IMAGE", {
        "prompt": "保留参考图商品外观，生成一张干净背景的商品展示图。",
        "image": f"data:{mime};base64,{encoded}",
        "response_format": "b64_json",
    })
    content = base64.b64decode(result["data"][0]["b64_json"], validate=True)
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif content.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    else:
        raise ValueError("生图接口未返回 PNG 或 JPEG")
    output = Path("data/model-probes/reference-result" + suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"模型调用失败（HTTP {error.code}）") from None
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise SystemExit("模型连接失败、返回格式不匹配或本地文件无法读取") from None
