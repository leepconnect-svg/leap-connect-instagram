"""
Anthropic API (文章生成・品質審査) と OpenAI Images API (画像生成) の薄いラッパー。
"""
import base64
import os

import requests

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")

# JSON出力専用のツール定義。自由記述のJSONをテキストとして出力させて後から
# json.loads()でパースする方式は、応答の途中切れ・書式崩れで壊れやすいため、
# Anthropicのtool use(構造化出力)機能を使い、モデルの応答自体をパース済みの
# 辞書として受け取る方式に統一する。
_EMIT_RESULT_TOOL = {
    "name": "emit_result",
    "description": "指示された内容の結果を構造化データとして返す",
    "input_schema": {"type": "object"},
}


def claude_json(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    images: list[bytes] | None = None,
    max_tokens: int = 4000,
) -> dict:
    """Anthropic Messages APIをtool use(強制的な構造化出力)で呼び、
    結果をパース済みの辞書として返す。
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
        tools=[_EMIT_RESULT_TOOL],
        tool_choice={"type": "tool", "name": "emit_result"},
        messages=[{"role": "user", "content": content}],
    )

    for block in resp.content:
        if block.type == "tool_use":
            return block.input

    # ここに来るのはmax_tokens不足でtool_use出力が完成しなかった場合等
    stop_reason = getattr(resp, "stop_reason", "unknown")
    raise RuntimeError(
        f"AIがtool_use形式の結果を返しませんでした(stop_reason={stop_reason})。"
        f"max_tokensを増やすか、プロンプトを見直してください。"
    )


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
