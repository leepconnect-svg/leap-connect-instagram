"""
STEP 5: AIによる投稿品質審査(100点満点)。
表紙画像等を実際に見せて(vision)評価させ、80点未満なら自動修正して再評価する。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from ai_clients import claude_json
from brand_context import BRAND_CONTEXT

REVIEW_SYSTEM_PROMPT = BRAND_CONTEXT + """

あなたの今回のタスクは、完成したInstagram投稿(6枚カルーセル)を
第三者の審査員として100点満点で厳しく採点することです。
甘い採点をせず、実際にこのアカウントのターゲット(東京の区分マンションオーナー)が
フィード上でこの投稿を見たときにどう反応するかを想像して評価してください。
"""

REVIEW_USER_PROMPT_TEMPLATE = """次の投稿を審査してください。1枚目と最終スライドの画像を添付します。

【テーマ】{theme}
【タイトル(1枚目)】{title}
【6枚の内容】
{slides_text}

【キャプション】
{caption}

【ハッシュタグ】
{hashtags}

以下の配点で採点してください(合計100点)。
- 1枚目の引き(スクロールを止める力): 20点
- 保存したくなる: 15点
- シェアしたくなる: 15点
- オーナーへの実用性: 15点
- 新規ユーザーへの分かりやすさ: 10点
- 空室・管理との関連性: 10点
- 独自性: 5点
- フォローする理由があるか: 10点

出力は以下のJSON形式のみ。

{{
  "scores": {{
    "hook_strength": 0〜20,
    "save_worthy": 0〜15,
    "share_worthy": 0〜15,
    "owner_utility": 0〜15,
    "clarity_for_new_users": 0〜10,
    "vacancy_management_relevance": 0〜10,
    "originality": 0〜5,
    "follow_reason": 0〜10
  }},
  "total": 0〜100,
  "strengths": ["良い点を1〜3個"],
  "issues": ["問題点を具体的に1〜4個(80点未満の場合は必須)"],
  "revision_instructions": "80点未満の場合、どう直すべきかの具体的な指示(1〜3文)。80点以上なら空文字でよい"
}}
"""


def _slides_text_block(script: dict) -> str:
    lines = []
    for i, s in enumerate(script["slides"], start=1):
        lines.append(f"{i}枚目[{s.get('role','')}] 見出し: {s.get('heading','')} / 本文: {s.get('body','')}")
    return "\n".join(lines)


def review_quality(anthropic_api_key: str, script: dict, image_paths: list[str]) -> dict:
    images = []
    for p in [image_paths[0], image_paths[-1]]:
        with open(p, "rb") as f:
            images.append(f.read())

    prompt = REVIEW_USER_PROMPT_TEMPLATE.format(
        theme=script.get("theme", ""),
        title=script.get("title", ""),
        slides_text=_slides_text_block(script),
        caption=script.get("caption", ""),
        hashtags=" ".join(script.get("hashtags", [])),
    )

    result = claude_json(anthropic_api_key, REVIEW_SYSTEM_PROMPT, prompt, images=images, max_tokens=4000)
    if "total" not in result:
        scores = result.get("scores", {})
        result["total"] = sum(scores.values()) if scores else 0
    return result


REVISE_SYSTEM_PROMPT = BRAND_CONTEXT + """

あなたの今回のタスクは、審査で指摘された問題点をもとに、
既存の6枚カルーセル台本を修正することです。
image_promptとroleは絶対に変更しないでください(写真は生成済みのため差し替えできません)。
heading・body・caption・hashtags・cta_textのみ改善してください。
"""

REVISE_USER_PROMPT_TEMPLATE = """以下の台本を、審査結果に基づいて修正してください。

【元の台本(JSON)】
{original_script}

【審査結果】
総合点: {total}/100
問題点: {issues}
修正指示: {revision_instructions}

出力は元と同じJSON構造(title, slides[6件、各役割role/heading/body/image_prompt], caption, hashtags, cta_text)で、
image_promptとroleは元の値をそのまま維持し、それ以外を改善してください。
"""


def revise_script(anthropic_api_key: str, script: dict, review_result: dict) -> dict:
    prompt = REVISE_USER_PROMPT_TEMPLATE.format(
        original_script=json.dumps(script, ensure_ascii=False),
        total=review_result.get("total", 0),
        issues="、".join(review_result.get("issues", [])),
        revision_instructions=review_result.get("revision_instructions", ""),
    )
    result = claude_json(anthropic_api_key, REVISE_SYSTEM_PROMPT, prompt, max_tokens=4000)

    # image_prompt/roleは元のスライドから強制的に引き継ぐ(写真との対応ズレを防ぐ)
    for i, slide in enumerate(result.get("slides", [])):
        if i < len(script["slides"]):
            slide["image_prompt"] = script["slides"][i]["image_prompt"]
            slide["role"] = script["slides"][i]["role"]

    for key in ("layout_type", "structure_type", "category", "theme", "sub_theme"):
        result[key] = script.get(key)

    return result


if __name__ == "__main__":
    print("review_quality(api_key, script, image_paths) / revise_script(api_key, script, review_result) を呼び出して使用してください")
