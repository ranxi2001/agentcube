#!/usr/bin/env python3
"""
gpt-image-draw - 使用 api.ai.tosky.top 图片 API 的 gpt-image-2 生成/编辑图片。

默认读取 API Key 优先级：
1. --api-key 参数
2. OPENAI_API_KEY 环境变量
3. IMAGE_API_KEY 环境变量
4. 当前目录 .env、仓库根 .env、~/.hermes/.env 中的同名变量

不会打印 API Key。
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少依赖：pip install openai") from exc


DEFAULT_BASE_URL = "https://api.ai.tosky.top/v1"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1254x1254"
SIZE_ALIASES = {
    "1:1": "1254x1254",
    "square": "1254x1254",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
    "3:4": "1086x1448",
    "4:3": "1448x1086",
    "4:5": "1122x1402",
    "5:4": "1402x1122",
    "16:9": "1672x941",
    "landscape": "1672x941",
    "9:16": "941x1672",
    "portrait": "941x1672",
    "21:9": "1915x821",
    "9:21": "821x1915",
}


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env() -> None:
    here = Path.cwd()
    candidates = [
        here / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for p in candidates:
        _load_env_file(p)


def resolve_api_key(cli_key: str | None = None) -> str:
    if cli_key:
        return cli_key
    load_env()
    for name in ("OPENAI_API_KEY", "IMAGE_API_KEY"):
        value = os.getenv(name)
        if value:
            return value
    raise SystemExit(
        "缺少 API Key：请设置 OPENAI_API_KEY 或 IMAGE_API_KEY，"
        "也可使用 --api-key 传入（注意不要把 key 提交到仓库）。"
    )


def read_prompt(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.prompt_file:
        parts.append(Path(args.prompt_file).read_text(encoding="utf-8"))
    if args.prompt:
        parts.append(args.prompt)
    prompt = "\n\n".join(p.strip() for p in parts if p and p.strip())
    if not prompt:
        raise SystemExit("缺少提示词：传入 prompt 参数或 --prompt-file")
    return prompt


def image_part_from_path(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"参考图不存在：{p}")
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def normalize_size(size: str) -> str:
    return SIZE_ALIASES.get(size, size)


def extract_image_bytes(response: Any) -> tuple[bytes, str]:
    data = response.model_dump() if hasattr(response, "model_dump") else response

    # /v1/images/generations 和 /v1/images/edits 常见格式：data[0].b64_json 或 data[0].url
    image_data = data.get("data") or []
    if image_data:
        item = image_data[0]
        if isinstance(item, dict):
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"]), "png"
            if item.get("url"):
                return bytes_from_url_or_data_url(item["url"])

    # 兼容 chat.completions 代理格式：message.images[0].image_url.url
    choices = data.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        images = msg.get("images") or []
        if images:
            url = (images[0].get("image_url") or {}).get("url") or images[0].get("url")
            if url:
                return bytes_from_url_or_data_url(url)

        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                url = None
                if item.get("type") in {"image_url", "output_image"}:
                    url = (item.get("image_url") or {}).get("url") or item.get("url")
                if url:
                    return bytes_from_url_or_data_url(url)

        if isinstance(content, str) and "data:image" in content and "base64," in content:
            start = content.find("data:image")
            token = content[start:].split()[0].strip('"\'`,)')
            return bytes_from_url_or_data_url(token)

    raise RuntimeError(f"未在响应中找到图片数据：{json.dumps(data, ensure_ascii=False)[:1000]}")


def bytes_from_url_or_data_url(url: str) -> tuple[bytes, str]:
    if url.startswith("data:image/"):
        header, b64_data = url.split(",", 1)
        ext = header.split("/")[1].split(";")[0] or "png"
        return base64.b64decode(b64_data), ext
    if url.startswith("http://") or url.startswith("https://"):
        with urlopen(url, timeout=120) as resp:
            content_type = resp.headers.get("Content-Type", "image/png")
            ext = content_type.split("/")[-1].split(";")[0] or "png"
            return resp.read(), ext
    raise RuntimeError(f"不支持的图片 URL 格式：{url[:80]}")


def build_messages(prompt: str, refs: list[str]) -> list[dict[str, Any]]:
    if not refs:
        return [{"role": "user", "content": prompt}]
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(image_part_from_path(p) for p in refs)
    return [{"role": "user", "content": content}]


def draw_image(
    prompt: str,
    output: str,
    *,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
    refs: list[str] | None = None,
) -> str:
    key = resolve_api_key(api_key)
    client = OpenAI(base_url=base_url, api_key=key)
    size = normalize_size(size)

    print("正在生成图片...")
    print(f"  模型: {model}")
    print(f"  尺寸: {size}")
    print(f"  提示词: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    if refs:
        print(f"  参考图: {len(refs)} 张")

    if refs:
        # 图片编辑 / 参考图模式：gpt-image-2 走 /v1/images/edits
        image_files = [open(p, "rb") for p in refs]
        try:
            response = client.images.edit(
                model=model,
                image=image_files if len(image_files) > 1 else image_files[0],
                prompt=prompt,
                size=size,
            )
        finally:
            for f in image_files:
                f.close()
    else:
        # 文生图模式：gpt-image-2 走 /v1/images/generations
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
        )
    img_bytes, ext = extract_image_bytes(response)

    out = Path(output)
    if out.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        out = out.with_suffix(f".{ext}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img_bytes)
    print(f"✓ 图片已保存: {out}")
    print(f"  文件大小: {out.stat().st_size:,} bytes")
    return str(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="使用 gpt-image-2 生成图片")
    parser.add_argument("prompt", nargs="?", help="绘图提示词")
    parser.add_argument("--prompt-file", help="从文件读取提示词")
    parser.add_argument("-o", "--output", default="output.png", help="输出文件路径")
    parser.add_argument("-s", "--size", default=DEFAULT_SIZE, help="尺寸比例或固定分辨率：1:1/2:3/3:2/3:4/4:3/4:5/5:4/16:9/9:16/21:9/9:21；gpt-image-2 当前固定 1.5K 档，quality 参数无效")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"模型名，默认 {DEFAULT_MODEL}")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL), help="OpenAI-compatible base URL")
    parser.add_argument("--api-key", help="API Key；默认从环境变量或 .env 读取")
    parser.add_argument("--ref", action="append", default=[], help="参考图路径，可多次传入")
    args = parser.parse_args()

    try:
        prompt = read_prompt(args)
        draw_image(
            prompt,
            args.output,
            model=args.model,
            size=args.size,
            base_url=args.base_url,
            api_key=args.api_key,
            refs=args.ref,
        )
        return 0
    except Exception as exc:
        print(f"✗ 生成失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
