"""
STEP 1: 今日の投稿テーマ候補をAIで複数(>=10)生成し、
過去投稿との重複・カテゴリ比率バランス・期待効果でスコアリングして1件選定する。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_clients import claude_json
from brand_context import BRAND_CONTEXT, CATEGORY_LIST, ANGLE_HINTS, STRUCTURE_TYPES
from db import db

SYSTEM_PROMPT = BRAND_CONTEXT + """

あなたの今回のタスクは、Instagram投稿の「テーマ候補」を複数作ることです。
1つの投稿は6枚のスライド(カルーセル)構成で、後工程で台本化されます。
ここではテーマの企画とその期待効果の自己評価のみを行ってください。
"""

USER_PROMPT_TEMPLATE = """次の条件でテーマ候補を{n}件作成してください。

【カテゴリ比率の目安(現在の重み)】
{category_weights}
※固定比率ではなく、参考値です。過去の実績で伸びているカテゴリを優先してよい。

【切り口のヒント(参考、これに縛られる必要はない)】
{angles}

【構成タイプの例】
{structures}

【重複禁止: 直近の投稿テーマ・タイトル一覧】
{recent}

【特に重要】
過去に「空室オーナー必見！空室を活用できるレンタルサロン活用法3選」というテーマの
反応が良かった実績があります。これは「空室×別用途×収益化」という構造が刺さった可能性が高い、
という仮説として扱ってください。ただしこの投稿のコピーは禁止です。
この構造(空室×別用途×収益化)を抽出しつつ、レンタルスペース/撮影スタジオ/ネイル/エステ/
パーソナルジム/SOHO/事務所/教室/会議室/法人利用/短期利用など、別の切り口で1〜2件は展開してください。
それ以外の候補は幅広いテーマ・カテゴリから作成してください。

出力は以下のJSON形式のみ。前後の説明文やコードブロック記号は付けないこと。

{{
  "candidates": [
    {{
      "theme": "投稿の中心テーマ(15字前後)",
      "sub_theme": "サブテーマ・具体的な切り口",
      "category": "{categories}のいずれか",
      "angle": "使用した切り口",
      "structure_type": "構成タイプ",
      "hook_idea": "1枚目に使えそうなフックの方向性(1文)",
      "scores": {{
        "follow_potential": 0〜10,
        "save_potential": 0〜10,
        "share_potential": 0〜10,
        "owner_utility": 0〜10,
        "sublease_relevance": 0〜10,
        "novelty": 0〜10,
        "buzz": 0〜10
      }}
    }}
    ... (合計{n}件)
  ]
}}
"""


_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {"type": "string"},
        "sub_theme": {"type": "string"},
        "category": {"type": "string"},
        "angle": {"type": "string"},
        "structure_type": {"type": "string"},
        "hook_idea": {"type": "string"},
        "scores": {
            "type": "object",
            "properties": {
                "follow_potential": {"type": "number"},
                "save_potential": {"type": "number"},
                "share_potential": {"type": "number"},
                "owner_utility": {"type": "number"},
                "sublease_relevance": {"type": "number"},
                "novelty": {"type": "number"},
                "buzz": {"type": "number"},
            },
            "required": [
                "follow_potential", "save_potential", "share_potential",
                "owner_utility", "sublease_relevance", "novelty", "buzz",
            ],
        },
    },
    "required": ["theme", "sub_theme", "category", "angle", "structure_type", "hook_idea", "scores"],
}

TOPICS_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {"type": "array", "items": _CANDIDATE_SCHEMA, "minItems": 8},
    },
    "required": ["candidates"],
}


def _category_overlap_adjustment(category: str, recent_posts: list[dict], category_weights: dict[str, float]) -> float:
    """直近投稿でのカテゴリ出現比率と目標重みを比較し、過少なら加点・過多なら減点する(-10〜+10)"""
    if not recent_posts:
        return 0.0
    total = len(recent_posts)
    count = sum(1 for p in recent_posts if p.get("category") == category)
    actual_ratio = count / total
    target_ratio = category_weights.get(category, 10.0) / sum(category_weights.values())
    diff = target_ratio - actual_ratio  # 正なら不足している(=加点すべき)
    return max(-10.0, min(10.0, diff * 100))


def score_candidate(candidate: dict, recent_posts: list[dict], category_weights: dict[str, float], overlap_penalty: float) -> float:
    s = candidate.get("scores", {})
    weighted = (
        s.get("follow_potential", 0) * 2.0
        + s.get("save_potential", 0) * 2.0
        + s.get("share_potential", 0) * 1.5
        + s.get("owner_utility", 0) * 1.5
        + s.get("sublease_relevance", 0) * 1.0
        + s.get("novelty", 0) * 1.0
        + s.get("buzz", 0) * 0.5
    )
    # 上記係数の合計は9.5、最大値10として正規化 → 満点95点相当。カテゴリ調整とかけあわせる
    category_bonus = _category_overlap_adjustment(candidate.get("category", ""), recent_posts, category_weights)
    return weighted - overlap_penalty * 30 + category_bonus


def generate_and_select_topic(anthropic_api_key: str, n_candidates: int = 10) -> dict:
    recent_posts = db.get_recent_posts(limit=30)
    recent_texts = [p.get("theme", "") for p in recent_posts] + [p.get("title", "") for p in recent_posts]
    recent_texts = [t for t in recent_texts if t]
    category_weights = db.get_category_weights()

    prompt = USER_PROMPT_TEMPLATE.format(
        n=n_candidates,
        category_weights=json.dumps(category_weights, ensure_ascii=False),
        angles="、".join(ANGLE_HINTS),
        structures="、".join(STRUCTURE_TYPES),
        recent="\n".join(f"- {t}" for t in recent_texts[-25:]) if recent_texts else "(まだ投稿履歴なし)",
        categories="/".join(CATEGORY_LIST),
    )

    result = claude_json(anthropic_api_key, SYSTEM_PROMPT, prompt, max_tokens=4000, tool_schema=TOPICS_TOOL_SCHEMA)
    candidates = result.get("candidates", [])
    # スキーマ上required指定していても、念のため必須キー欠落分は除外しておく
    candidates = [c for c in candidates if {"theme", "category"}.issubset(c.keys())]
    if not candidates:
        raise RuntimeError(f"テーマ候補が生成されませんでした: {result}")

    scored = []
    for c in candidates:
        theme_text = f"{c.get('theme','')} {c.get('sub_theme','')}"
        too_similar, matched = db.is_too_similar_to_recent(theme_text, recent_texts, threshold=0.72)
        penalty = 1.0 if too_similar else 0.0
        total = score_candidate(c, recent_posts, category_weights, penalty)
        scored.append((total, c, too_similar, matched))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 重複していない候補を優先的に選ぶ。全滅なら最高得点のものを使う(ログに警告)
    non_dupe = [x for x in scored if not x[2]]
    chosen_score, chosen, is_dupe, matched = (non_dupe[0] if non_dupe else scored[0])

    if is_dupe:
        print(f"[WARN] 選定テーマが過去投稿と類似しています(類似元: {matched})。企画AIへの再指示を検討してください。", file=sys.stderr)

    chosen["_score"] = chosen_score
    chosen["_all_candidates"] = [c for _, c, _, _ in scored]

    db.record_topic_usage(chosen["theme"], chosen.get("category", ""), chosen_score)
    return chosen


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY が未設定です", file=sys.stderr)
        sys.exit(1)
    topic = generate_and_select_topic(api_key)
    print(json.dumps(topic, ensure_ascii=False, indent=2))
