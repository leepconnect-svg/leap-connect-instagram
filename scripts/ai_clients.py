"""
Anthropic API (文章生成・品質審査) と OpenAI Images API (画像生成) の薄いラッパー。
"""
import base64
import json
import os
import re

import requests

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    return json.loads(text.strip())


def claude_json(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    images: list[bytes] | None = None,
    max_tokens: int = 4000,
) -> dict:
    """Anthropic Messages APIを呼び、JSON形式のレスポンスをパースして返す。
    imagesを渡すとvision入力(品質審査で表紙画像を見せる用途)として送信する。"""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    content = []
    if images:
        for img_bytes in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(img_bytes).decode("utf-8"),
                    },
                }
            )
    content.append({"type": "text", "text": user_prompt})

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )

    text_parts = [block.text for block in resp.content if block.type == "text"]
    full_text = "\n".join(text_parts)
    return _extract_json(full_text)


def generate_image_openai(api_key: str, prompt: str, size: str = "1024x1536", quality: str = "medium") -> bytes:
    """OpenAI Images API (gpt-image-1)で画像を生成し、PNGバイト列を返す"""
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI Image API error {resp.status_code}: {resp.text}")
    data = resp.json()
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)
