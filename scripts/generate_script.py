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
from brand_context import BRAND_CONTEXT, CTA_EXAMPLES, IMPLEMENTED_LAYOUTS, LAYOUT_DESCRIPTIONS, SPACE_USE_CASES
from db import db

_VACANCY_KEYWORDS = ("別用途", "多用途", "時間貸し", "スペースマーケット") + tuple(SPACE_USE_CASES)


def is_vacancy_reuse_topic(topic: dict) -> bool:
    """テーマが「空室の時間貸し/多用途活用」系かどうかを判定する"""
    text = " ".join([topic.get("theme", ""), topic.get("sub_theme", ""), topic.get("angle", "")])
    return any(kw in text for kw in _VACANCY_KEYWORDS)

SYSTEM_PROMPT = BRAND_CONTEXT + """

あなたの今回のタスクは、決定済みのテーマから
Instagramカルーセル投稿(6枚)の台本一式を作ることです。

【6枚の設計原則】
・スライドは必ずちょうど6枚(1枚目のhookと6枚目のsummary_ctaを含めて6枚)。
  絶対にこれより多くても少なくてもいけない
・テーマが「5選」「7つの」のような数字を含む場合でも、実際に作るコンテンツ項目は
  「6枚 - hook(1枚) - summary_cta(1枚) = 4項目」に収める。
  例えば元テーマが「空室が長引く理由5選」であっても、見出し(title/heading)は
  「4つのポイント」のように実際の項目数に合わせて言い換えるか、
  5項目のうち重要度の低いものを1つ削って4項目に絞ること
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
  オートロック, 修繕作業, 清掃, 内見風景, 空室, パーティールーム風内装, レンタルスタジオ,
  貸し会議室, 撮影スタジオ, レンタルサロン風内装, プライベートジム風内装, ポップアップストア風の
  ディスプレイ空間, コワーキングスペース, SOHO/オフィス 等からテーマに合うものを選ぶ)

各スライドにはさらに以下の2つも付けてください:
・emphasis: heading内の一部分をそのまま抜き出した文字列(色を変えて強調表示するために使う)。
  headingの中に実際に含まれる連続した文字列でなければならない(存在しない語は不可)。
  強調するほどの語がなければ空文字("")でよい
・bullets: 見た瞬間に読める短いテキスト(8〜14字程度)を0〜2個の配列で。
  「知らないと損するかも！」のような、続きが気になる一言。
  1枚目(hook)と最後(summary_cta)には1〜2個入れることを推奨。
  中間スライドでは無理に入れず空配列([])でよい

法令・管理規約・用途変更等に関わる内容を含む場合は、
「物件・地域・契約条件によって異なります」等の注意書きをどこかのスライドかキャプションに入れてください。

出力は以下のJSON形式のみ。

{{
  "title": "1枚目に表示するタイトル(20字前後)",
  "slides": [
    {{"role": "hook", "heading": "1枚目の見出し", "body": "1枚目の補足文(あれば、なければ空文字)", "image_prompt": "...", "emphasis": "...", "bullets": ["...", "..."]}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "...", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "summary_cta", "heading": "まとめの見出し", "body": "CTA文", "image_prompt": "...", "emphasis": "...", "bullets": ["...", "..."]}}
  ],
  "caption": "本文キャプション(200〜400字、絵文字は控えめに)",
  "hashtags": ["#...", "... 10〜15個"],
  "cta_text": "6枚目に使ったCTA文と同じもの"
}}

slides配列の要素数は必ずちょうど6にしてください(5でも7でも不可)。
"""

VACANCY_REUSE_PROMPT_TEMPLATE = """次のテーマで「空室の時間貸し/多用途活用」専用の台本を作成してください。
このテーマは決まった6枚構成を使います(他のテーマの構成とは違うので注意)。

テーマ: {theme}
サブテーマ: {sub_theme}
カテゴリ: {category}
用途例のローテーション候補(3つ選ぶ。過去投稿と同じ組み合わせは避ける): {space_use_cases}

【6枚の決まった構成】
1. hook: 「(用途1)を活用できる(用途1)活用法3選」のような表紙。フックとして強い言い切り
2. problem: 「なぜ今、空室の多用途活用が注目されるのか」等、自分ごと化させる問題提起
3. method_1: 提案する用途1つ目。見出しに用途名を入れる。本文で「どんな物件に向いているか」
   「メリット」を簡潔に(40字程度)
4. method_2: 用途2つ目。method_1と同じ構成、内容は別の用途
5. method_3: 用途3つ目。method_1と同じ構成、内容はさらに別の用途
6. summary_cta: 「空室のまま眠らせていませんか？」のようなまとめ。bulletsに今回扱った3つの
   用途を短く列挙し(例: "賃貸", "レンタルサロン", "その他の活用")、
   本文は「物件に合わせた収益化方法を考えます」のような相談誘導、CTAは相談を促す文言

各スライドのimage_promptの条件:
・実在する特定物件を想起させない一般的な室内写真であること
・"no text, no letters, no watermark" を必ず含める
・清潔感・自然光・高級感のある日本のマンションを想定した室内(過剰な高級ホテル風は禁止)
・method_1〜3では、その用途が一目で伝わる家具/設備を配置する
  (例: レンタルサロン→施術ベッド・鏡・観葉植物、レンタルオフィス→デスク・チェア・PC、
  撮影スタジオ→照明・背景、貸し会議室→テーブル・チェア・モニター、
  プライベートジム→トレーニング機器、ポップアップストア→ディスプレイ棚)

各スライドにはさらに以下の2つも付けてください:
・emphasis: heading内の一部分をそのまま抜き出した文字列(色を変えて強調表示するために使う、
  用途名や数字など)。headingに実際に含まれる文字列でなければならない。無ければ空文字
・bullets: 短いテキスト(8〜14字程度)の配列。hookには2個、summary_ctaには今回扱った3用途を
  短縮して3個、中間スライド(problem/method_1〜3)は空配列([])でよい

必ず「管理規約・賃貸借契約・用途地域・建築/消防関係等の確認が必要な場合がある」旨を
どこかのスライドかキャプションに入れてください(どんな物件でも使えると断定しない)。

出力は以下のJSON形式のみ。

{{
  "title": "1枚目に表示するタイトル(20字前後)",
  "slides": [
    {{"role": "hook", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": ["...", "..."]}},
    {{"role": "problem", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "method_1", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "method_2", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "method_3", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": []}},
    {{"role": "summary_cta", "heading": "...", "body": "...", "image_prompt": "...", "emphasis": "...", "bullets": ["...", "...", "..."]}}
  ],
  "caption": "本文キャプション(200〜400字、絵文字は控えめに)",
  "hashtags": ["#...", "... 10〜15個"],
  "cta_text": "6枚目に使ったCTA文と同じもの"
}}

slides配列の要素数は必ずちょうど6にしてください。role名は上記の通り固定です。
"""

_RETRY_NOTE = """

【重要・厳守】前回の出力はslidesが{actual}件でした。ちょうど6件にしてください。
テーマの数字表現(「5選」等)と実際の項目数が一致しなくても構いません。
見出しの文言を項目数に合わせて調整してください。
"""

_SLIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string"},
        "heading": {"type": "string"},
        "body": {"type": "string"},
        "image_prompt": {"type": "string"},
        "emphasis": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": ["role", "heading", "body", "image_prompt", "emphasis", "bullets"],
}

# 必須キーの欠落(例: hashtagsが無い等)を防ぐため、明示的なJSON Schemaを渡す。
SCRIPT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "slides": {
            "type": "array",
            "items": _SLIDE_SCHEMA,
            "minItems": 6,
            "maxItems": 6,
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 8},
        "cta_text": {"type": "string"},
    },
    "required": ["title", "slides", "caption", "hashtags", "cta_text"],
}


# Kは実績のある過去投稿を再現したレイアウトなので、どの構成タイプでも最優先候補にする
LAYOUT_AFFINITY = {
    "チェックリスト型": ["K", "C", "J", "A"],
    "ランキング型": ["K", "G", "A", "J"],
    "数字型": ["K", "G", "A"],
    "問題→原因→対策型": ["K", "E", "A", "J"],
    "Before/After型": ["K", "E", "A"],
    "比較型": ["K", "J", "E"],
    "誤解→正解型": ["K", "E", "J"],
    "Q&A型": ["K", "J", "A"],
    "診断型": ["K", "C", "J"],
    "ストーリー型": ["K", "I", "A"],
    "一般論としてのケース型": ["K", "I", "A", "J"],
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
    vacancy_reuse = is_vacancy_reuse_topic(topic)

    if vacancy_reuse:
        prompt = VACANCY_REUSE_PROMPT_TEMPLATE.format(
            theme=topic.get("theme", ""),
            sub_theme=topic.get("sub_theme", ""),
            category=topic.get("category", ""),
            space_use_cases="、".join(SPACE_USE_CASES),
        )
    else:
        prompt = USER_PROMPT_TEMPLATE.format(
            theme=topic.get("theme", ""),
            sub_theme=topic.get("sub_theme", ""),
            category=topic.get("category", ""),
            angle=topic.get("angle", ""),
            structure_type=topic.get("structure_type", ""),
            hook_idea=topic.get("hook_idea", ""),
        )
    system = SYSTEM_PROMPT.format(cta_examples="\n  ".join(f"- {c}" for c in CTA_EXAMPLES))

    result = claude_json(anthropic_api_key, system, prompt, max_tokens=4000, tool_schema=SCRIPT_TOOL_SCHEMA)
    slides = result.get("slides", [])

    # 6枚ちょうどでなければ、修正指示を添えて最大2回まで再試行する
    for _ in range(2):
        required_keys = {"title", "slides", "caption", "hashtags", "cta_text"}
        if len(slides) == 6 and required_keys.issubset(result.keys()):
            break
        retry_prompt = prompt + _RETRY_NOTE.format(actual=len(slides))
        result = claude_json(anthropic_api_key, system, retry_prompt, max_tokens=4000, tool_schema=SCRIPT_TOOL_SCHEMA)
        slides = result.get("slides", [])

    missing = {"title", "slides", "caption", "hashtags", "cta_text"} - result.keys()
    if missing:
        raise RuntimeError(f"台本の必須項目が欠落しています({missing}): {result}")
    if len(slides) != 6:
        raise RuntimeError(f"スライドが6枚ではありません(実際: {len(slides)}枚): {result}")

    for slide in slides:
        slide["image_prompt"] = slide.get("image_prompt", "").strip() + IMAGE_PROMPT_SUFFIX

    # 空室多用途活用テーマは、その専用に作ったレイアウトKを常に使う
    result["layout_type"] = "K" if vacancy_reuse else choose_layout(topic.get("structure_type", ""))
    result["structure_type"] = "空室活用3提案型" if vacancy_reuse else topic.get("structure_type", "")
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
