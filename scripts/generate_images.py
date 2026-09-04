"""
STEP 3: 台本の各スライドのimage_promptから、OpenAI Images API (gpt-image-1)で
背景写真を生成する。直近使用したプロンプトと似すぎている場合は変化を加えて再生成する。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image

from ai_clients import generate_image_openai
from db import db

VARIATION_HINTS = [
    "different angle",
    "different time of day, softer light",
    "different room layout",
    "different color palette of furnishings",
    "wider composition",
]


def _too_similar_to_recent(prompt: str, recent_prompts: list[str], threshold: float = 0.85) -> bool:
    too_similar, _ = db.is_too_similar_to_recent(prompt, recent_prompts, threshold=threshold)
    return too_similar


def generate_slide_images(openai_api_key: str, image_prompts: list[str], theme: str, out_dir: str, post_id: str | None = None) -> list[str]:
    """image_promptsのリスト(6件)から画像を生成し、保存パスのリストを返す"""
    os.makedirs(out_dir, exist_ok=True)
    recent_prompts = db.get_recent_prompts(limit=60)

    paths = []
    for i, prompt in enumerate(image_prompts):
        final_prompt = prompt
        if _too_similar_to_recent(prompt, recent_prompts):
            hint = VARIATION_HINTS[i % len(VARIATION_HINTS)]
            final_prompt = f"{prompt}, {hint}"

        img_bytes = generate_image_openai(openai_api_key, final_prompt, size="1024x1536", quality="medium")
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        path = os.path.join(out_dir, f"raw_{i:02d}.png")
        img.save(path)
        paths.append(path)
        recent_prompts.append(final_prompt)  # 同一バッチ内での重複も避ける

        if post_id:
            db.record_creative_asset(post_id, i, path, final_prompt, theme)

    return paths


if __name__ == "__main__":
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY が未設定です", file=sys.stderr)
        sys.exit(1)
    prompts = [
        "modern Tokyo apartment building exterior, blue sky, no text, no letters, no watermark",
    ]
    out = generate_slide_images(api_key, prompts, theme="test", out_dir=os.path.join(os.path.dirname(__file__), "..", "data", "test_images"))
    print(out)
