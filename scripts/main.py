"""
leap_connect Instagram自動化システム メインオーケストレーター(フェーズ1+2)

流れ:
  ① テーマ企画(重複チェック・スコアリング込み)
  ② 6枚台本生成(見出し/本文/画像プロンプト/キャプション/ハッシュタグ/CTA)
  ③ AI画像生成(OpenAI)
  ④ ブランドデザインでの画像合成(Pillow、日本語をプログラムで配置)
  ⑤ AI品質審査(100点満点) → 80点未満なら自動修正して再審査(最大2回)
  ⑥ (DRY_RUN=0の場合)Instagram公式APIへ投稿
  ⑦ DBへ記録

エラー処理: どのステージで失敗しても、無理に投稿はしない(status=failed/rejectedで停止)。
"""
import datetime
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import db
from generate_topics import generate_and_select_topic
from generate_script import generate_script
from generate_images import generate_slide_images
from compose_slides import compose_slides
from quality_review import review_quality, revise_script
from publish_images import publish_images_to_github
from post_instagram import post_carousel

ROOT = os.path.join(os.path.dirname(__file__), "..")
QUALITY_THRESHOLD = int(os.environ.get("QUALITY_THRESHOLD", "80"))
MAX_REVISIONS = 2


def require_env(*names: str) -> dict:
    values, missing = {}, []
    for name in names:
        v = os.environ.get(name)
        if not v:
            missing.append(name)
        values[name] = v
    if missing:
        print(f"[ERROR] 必須の環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return values


def build_caption(script: dict) -> str:
    hashtags = " ".join(script.get("hashtags", []))
    return f"{script['caption']}\n.\n.\n.\n{hashtags}"


def validate_script_and_images(script: dict, image_paths: list[str]) -> list[str]:
    """投稿前の最終チェック。問題があればエラー内容のリストを返す(空なら問題なし)"""
    errors = []
    if len(script.get("slides", [])) != 6:
        errors.append(f"スライド数が6枚ではありません: {len(script.get('slides', []))}枚")
    if len(image_paths) != 6:
        errors.append(f"生成された画像が6枚ではありません: {len(image_paths)}枚")
    for p in image_paths:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            errors.append(f"画像ファイルが不正です: {p}")
    if not script.get("caption"):
        errors.append("キャプションが空です")
    if not script.get("hashtags"):
        errors.append("ハッシュタグが空です")
    return errors


def fail(post_id: str, reason: str) -> None:
    print(f"[FAIL] {reason}", file=sys.stderr)
    db.update_post(post_id, status="failed", reject_reason=reason)


def main():
    dry_run = os.environ.get("DRY_RUN", "1") == "1"
    brand_handle = os.environ.get("BRAND_HANDLE", "@leap_connect")

    required = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    if not dry_run:
        required += ["IG_USER_ID", "IG_ACCESS_TOKEN"]
    env = require_env(*required)

    db.init_db()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = os.path.join(ROOT, "data", "generated", timestamp)

    print("[1/7] テーマ企画中...")
    topic = generate_and_select_topic(env["ANTHROPIC_API_KEY"])
    print(f"  テーマ: {topic['theme']} / カテゴリ: {topic.get('category')} / スコア: {topic.get('_score'):.1f}")

    print("[2/7] 6枚台本を生成中...")
    script = generate_script(env["ANTHROPIC_API_KEY"], topic)
    print(f"  タイトル: {script['title']} / レイアウト: {script['layout_type']} ({script['structure_type']})")

    post_id = db.create_post(
        date=timestamp[:8],
        theme=script["theme"],
        sub_theme=script.get("sub_theme"),
        category=script.get("category"),
        structure_type=script.get("structure_type"),
        layout_type=script["layout_type"],
        title=script["title"],
        slide_texts=script["slides"],
        caption=script["caption"],
        hashtags=script["hashtags"],
        cta_text=script.get("cta_text"),
        status="draft",
    )
    db.record_layout_usage(script["layout_type"], post_id)
    print(f"  post_id = {post_id}")

    try:
        print("[3/7] AI画像を生成中(OpenAI)...")
        image_prompts = [s["image_prompt"] for s in script["slides"]]
        raw_photo_paths = generate_slide_images(
            env["OPENAI_API_KEY"], image_prompts, theme=script["theme"],
            out_dir=os.path.join(work_dir, "raw"), post_id=post_id,
        )
        print(f"  {len(raw_photo_paths)}枚生成完了")

        print("[4/7] 画像を合成中(ブランドデザイン適用)...")
        image_paths = compose_slides(script, raw_photo_paths, out_dir=os.path.join(work_dir, "final"), brand_handle=brand_handle)
        db.update_post(post_id, image_paths=image_paths, image_prompts=image_prompts)
        print(f"  {len(image_paths)}枚合成完了: {work_dir}")

    except Exception:
        fail(post_id, f"画像生成/合成でエラー:\n{traceback.format_exc()}")
        sys.exit(1)

    print("[5/7] AI品質審査中...")
    try:
        review = review_quality(env["ANTHROPIC_API_KEY"], script, image_paths)
        attempt = 0
        while review.get("total", 0) < QUALITY_THRESHOLD and attempt < MAX_REVISIONS:
            attempt += 1
            print(f"  {review.get('total')}点 (< {QUALITY_THRESHOLD}点) のため自動修正中... (試行{attempt}/{MAX_REVISIONS})")
            print(f"  指摘: {review.get('issues')}")
            script = revise_script(env["ANTHROPIC_API_KEY"], script, review)
            image_paths = compose_slides(script, raw_photo_paths, out_dir=os.path.join(work_dir, f"final_r{attempt}"), brand_handle=brand_handle)
            review = review_quality(env["ANTHROPIC_API_KEY"], script, image_paths)

        print(f"  最終スコア: {review.get('total')}点 (試行回数: {attempt})")
        db.update_post(
            post_id,
            quality_score=review.get("total"),
            quality_breakdown=review,
            revision_count=attempt,
            slide_texts=script["slides"],
            caption=script["caption"],
            hashtags=script["hashtags"],
            cta_text=script.get("cta_text"),
            image_paths=image_paths,
        )

        if review.get("total", 0) < QUALITY_THRESHOLD:
            fail(post_id, f"品質スコアが{QUALITY_THRESHOLD}点未満のため投稿を中止しました(最終{review.get('total')}点)。issues={review.get('issues')}")
            sys.exit(1)

    except Exception:
        fail(post_id, f"品質審査でエラー:\n{traceback.format_exc()}")
        sys.exit(1)

    print("[6/7] 最終バリデーション中...")
    errors = validate_script_and_images(script, image_paths)
    if errors:
        fail(post_id, f"最終バリデーションエラー: {errors}")
        sys.exit(1)

    caption = build_caption(script)
    db.update_post(post_id, status="ready")

    if dry_run:
        print("[DRY_RUN] Instagramへの投稿はスキップしました")
        print("--- caption ---")
        print(caption)
        print(f"--- 画像 ({len(image_paths)}枚) ---")
        for p in image_paths:
            print(f"  {p}")
        return

    print("[7/7] Instagramへ投稿中...")
    try:
        print("  画像をリポジトリに公開中(GitHub + jsdelivr)...")
        image_urls = publish_images_to_github(image_paths, repo_root=ROOT)
        for u in image_urls:
            print(f"    {u}")
        time.sleep(3)  # CDNが新規ファイルを認識するまでの安全マージン
        media_id = post_carousel(env["IG_USER_ID"], env["IG_ACCESS_TOKEN"], image_urls, caption)
        db.update_post(post_id, status="posted", ig_media_id=media_id, posted_at=db.now_iso())
        print(f"  公開しました: media_id={media_id}")
    except Exception:
        fail(post_id, f"Instagram投稿でエラー:\n{traceback.format_exc()}")
        sys.exit(1)

    print("完了しました。")


if __name__ == "__main__":
    main()
