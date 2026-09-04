"""
STEP 2: 選定されたテーマから、6枚カルーセルの台本(見出し/本文/画像プロンプト)、
キャプション、ハッシュタグ、CTAを生成する。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_clients import claude_json
from brand_context import BRAND_CONTEXT, CTA_EXAMPLES, IMPLEMENTED_LAYOUTS, LAYOUT_DESCRIPTIONS
from db import db

SYSTEM_PROMPT = BRAND_CONTEXT + """

あなたの今回のタスクは、決定済みのテーマから
Instagramカルーセル投稿(6枚)の台本一式を作ることです。

【6枚の設計原則】
・毎日同じ構成をコピーしない。指定された構成タイプに合わせて6枚を設計する
・1枚目は最重要。新規ユーザーが「自分に関係ある」と思う具体的なタイトルにする。
  会社紹介や営業文句から始めない。「オーナー必見！」のような紋切り型だけで終わらせない。
  煽りすぎない。事実ではない断定をしない
・投稿内容に応じて、オーナーにとっての具体的な損失(賃料減少・修繕費増加・長期空室・
  クレーム増加・物件価値低下・時間/手間の損失等)に触れる箇所を含める
・6枚目はまとめ+自然なCTA。CTAは以下の例のトーンを参考にしつつ、
  必ず違う言い回しにする(同じ文言の使い回し禁止):
  {cta_examples}
・キャプションは (1)冒頭1〜2行で興味を引く (2)投稿内容の補足 (3)オーナーが知っておくべきポイント
  (4)注意点 (5)自然なCTA、の流れ。営業感を出しすぎない
・ハッシュタグは投稿内容との関連性を優先し、毎回同じ羅列にしない(10〜15個)
"""

USER_PROMPT_TEMPLATE = """次のテーマで台本を作成してください。

テーマ: {theme}
サブテーマ: {sub_theme}
カテゴリ: {category}
切り口: {angle}
構成タイプ: {structure_type}
フックの方向性: {hook_idea}

各スライドには画像生成用のプロンプト(image_prompt)を英語で付けてください。条件:
・実在する特定物件を想起させない、一般的なマンション/室内/設備等の写真であること
・"no text, no letters, no watermark" を必ず含め、文字入りの画像にならないようにする
・プロフェッショナルな不動産写真/建築写真のスタイル(自然光、清潔感、高級感)
・6枚それぞれ異なる被写体にする(例: 外観, 室内, 共用廊下, 宅配ボックス, エアコン, 給湯器,
  オートロック, 修繕作業, 清掃, 内見風景, 空室, レンタルサロン風内装, SOHO/オフィス, 撮影スタジオ 等から
  テーマに合うものを選ぶ)

法令・管理規約・用途変更等に関わる内容を含む場合は、
「物件・地域・契約条件によって異なります」等の注意書きをどこかのスライドかキャプションに入れてください。

出力は以下のJSON形式のみ。

{{
  "title": "1枚目に表示するタイトル(20字前後)",
  "slides": [
    {{"role": "hook", "heading": "1枚目の見出し", "body": "1枚目の補足文(あれば、なければ空文字)", "image_prompt": "..."}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "..."}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "..."}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "..."}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "..."}},
    {{"role": "summary_cta", "heading": "まとめの見出し", "body": "CTA文", "image_prompt": "..."}}
  ],
  "caption": "本文キャプション(200〜400字、絵文字は控えめに)",
  "hashtags": ["#...", "... 10〜15個"],
  "cta_text": "6枚目に使ったCTA文と同じもの"
}}

slidesは必ず6件にしてください。
"""


LAYOUT_AFFINITY = {
    "チェックリスト型": ["C", "J", "A"],
    "ランキング型": ["G", "A", "J"],
    "数字型": ["G", "A"],
    "問題→原因→対策型": ["E", "A", "J"],
    "Before/After型": ["E", "A"],
    "比較型": ["J", "E"],
    "誤解→正解型": ["E", "J"],
    "Q&A型": ["J", "A"],
    "診断型": ["C", "J"],
    "ストーリー型": ["I", "A"],
    "一般論としてのケース型": ["I", "A", "J"],
}


def choose_layout(structure_type: str) -> str:
    """構成タイプに合うレイアウトを、直近使用したものを避けて選ぶ"""
    recent = set(db.get_recent_layouts(limit=2))
    preferred = LAYOUT_AFFINITY.get(structure_type, list(IMPLEMENTED_LAYOUTS))
    for layout in preferred:
        if layout in IMPLEMENTED_LAYOUTS and layout not in recent:
            return layout
    for layout in IMPLEMENTED_LAYOUTS:
        if layout not in recent:
            return layout
    return IMPLEMENTED_LAYOUTS[0]


IMAGE_PROMPT_SUFFIX = (
    ", no text, no letters, no watermark, no logo, photorealistic professional real estate photography, "
    "natural lighting, clean and upscale atmosphere, navy and gold accent tones where natural, 4:5 vertical composition"
)


def generate_script(anthropic_api_key: str, topic: dict) -> dict:
    prompt = USER_PROMPT_TEMPLATE.format(
        theme=topic.get("theme", ""),
        sub_theme=topic.get("sub_theme", ""),
        category=topic.get("category", ""),
        angle=topic.get("angle", ""),
        structure_type=topic.get("structure_type", ""),
        hook_idea=topic.get("hook_idea", ""),
    )
    system = SYSTEM_PROMPT.format(cta_examples="\n  ".join(f"- {c}" for c in CTA_EXAMPLES))

    result = claude_json(anthropic_api_key, system, prompt, max_tokens=4000)

    slides = result.get("slides", [])
    if len(slides) != 6:
        raise RuntimeError(f"スライドが6枚ではありません(実際: {len(slides)}枚): {result}")

    for slide in slides:
        slide["image_prompt"] = slide.get("image_prompt", "").strip() + IMAGE_PROMPT_SUFFIX

    result["layout_type"] = choose_layout(topic.get("structure_type", ""))
    result["structure_type"] = topic.get("structure_type", "")
    result["category"] = topic.get("category", "")
    result["theme"] = topic.get("theme", "")
    result["sub_theme"] = topic.get("sub_theme", "")
    return result


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY が未設定です", file=sys.stderr)
        sys.exit(1)
    sample_topic = {
        "theme": "空室を活かすレンタルスペース化",
        "sub_theme": "撮影スタジオとしての活用",
        "category": "空室",
        "angle": "空室の別用途活用",
        "structure_type": "チェックリスト型",
        "hook_idea": "その空室、家賃以外の使い道があるかもしれません",
    }
    script = generate_script(api_key, sample_topic)
    print(json.dumps(script, ensure_ascii=False, indent=2))
