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
from repost_existing import repost_post

ROOT = os.path.join(os.path.dirname(__file__), "..")
QUALITY_THRESHOLD = int(os.environ.get("QUALITY_THRESHOLD", "72"))
MAX_REVISIONS = 2
# オーナーが「このテスト内容を次回9時に確実に投稿して」と指示した場合に使う予約マーカー。
# ここにpost_idが書かれていると、通常の生成パイプラインをスキップしてその投稿を直接公開し、
# 消費後はファイルを削除して次回以降は通常運転に戻す(1日1投稿を守るため、
# 通常生成とは絶対に両方実行しない)
RESERVED_POST_PATH = os.path.join(ROOT, "data", "reserved_post_id.txt")


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
    """本物のエラー(バグ・API障害等)。GitHub Actions上でも失敗(赤いX)として扱うべきもの"""
    print(f"[FAIL] {reason}", file=sys.stderr)
    db.update_post(post_id, status="failed", reject_reason=reason)


def reject(post_id: str, reason: str) -> None:
    """意図した安全装置が働いた結果(品質スコア未達等)。バグではないため、
    GitHub Actions上は成功(緑)のまま終わらせ、失敗通知メールで誤って
    「システムエラー」だと誤解されないようにする"""
    print(f"[REJECTED] {reason}")
    db.update_post(post_id, status="rejected", reject_reason=reason)


def main():
    dry_run = os.environ.get("DRY_RUN", "1") == "1"
    brand_handle = os.environ.get("BRAND_HANDLE", "@leap_connect")

    # 予約投稿(オーナーが確認済みのテスト内容を「次回9時に確実に投稿して」と指示した場合)が
    # あれば、通常の生成パイプラインは一切実行せず、それだけを投稿して終了する。
    # 1日1投稿を守るため、予約投稿と通常生成を同じ実行で両方行うことは絶対にしない。
    if os.path.exists(RESERVED_POST_PATH):
        with open(RESERVED_POST_PATH, encoding="utf-8") as f:
            reserved_id = f.read().strip()
        if reserved_id:
            print(f"[RESERVED] 予約済みの投稿を優先実行します: post_id={reserved_id}")
            ig_env = require_env("IG_USER_ID", "IG_ACCESS_TOKEN") if not dry_run else {}
            try:
                repost_post(reserved_id, ig_env.get("IG_USER_ID"), ig_env.get("IG_ACCESS_TOKEN"), ROOT, dry_run=dry_run)
            finally:
                # 成功/失敗にかかわらず一度きりの予約として消費し、次回以降は通常運転に戻す
                os.remove(RESERVED_POST_PATH)
            return
        os.remove(RESERVED_POST_PATH)

    required = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    if not dry_run:
        required += ["IG_USER_ID", "IG_ACCESS_TOKEN"]
    env = require_env(*required)

    db.init_db()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = os.path.join(ROOT, "data", "generated", timestamp)

    print("[1/7] テーマ企画中...")
    force_theme = os.environ.get("FORCE_THEME")
    if force_theme == "vacancy_reuse":
        # 動作確認用: 「空室の時間貸し/多用途活用」テーマを強制的に選ぶ(通常のランダム選定を迂回)
        print("  [FORCE_THEME=vacancy_reuse] テーマ選定をスキップし、空室活用3提案型を強制指定")
        topic = {
            "theme": "空室を活かす多用途活用術",
            "sub_theme": "時間貸しでの収益化",
            "category": "空室",
            "angle": "空室の別用途活用(時間貸し/多用途活用)",
            "structure_type": "チェックリスト型",
            "hook_idea": "家賃以外の使い道がある",
            "_score": 0.0,
        }
    elif force_theme == "minpaku_reuse":
        # 動作確認用: 「民泊規制強化からの転用」テーマを強制的に選ぶ
        print("  [FORCE_THEME=minpaku_reuse] テーマ選定をスキップし、民泊からの転用を強制指定")
        topic = {
            "theme": "民泊をやめた部屋の次の使い道",
            "sub_theme": "民泊規制強化と時間貸しへの転用",
            "category": "空室",
            "angle": "民泊規制強化からの転用(民泊をやめた部屋の次の使い道)",
            "structure_type": "チェックリスト型",
            "hook_idea": "民泊の稼働日数、上限に達していませんか",
            "_score": 0.0,
        }
    else:
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
        quality_passed = review.get("total", 0) >= QUALITY_THRESHOLD

    except Exception:
        fail(post_id, f"品質審査でエラー:\n{traceback.format_exc()}")
        sys.exit(1)

    # 品質基準を満たさなかった場合も、確認できるように画像だけはリポジトリに残す
    # (Instagramへの投稿は絶対にしない)
    print("[6/7] 画像をリポジトリに公開中(GitHub + jsdelivr、確認用)...")
    try:
        image_urls = publish_images_to_github(image_paths, repo_root=ROOT)
        for u in image_urls:
            print(f"    {u}")
    except Exception:
        fail(post_id, f"画像の公開でエラー:\n{traceback.format_exc()}")
        sys.exit(1)

    if not quality_passed:
        # これはバグではなく、安全装置(品質ゲート)が意図通り働いた結果。
        # sys.exit(1)にするとGitHub Actionsが「失敗」として赤いX+失敗通知メールを
        # 送ってしまい、正常動作にもかかわらず「システムエラー」と誤解されるため
        # 正常終了(exit 0)にする
        reject(post_id, f"品質スコアが{QUALITY_THRESHOLD}点未満のため投稿を中止しました(最終{review.get('total')}点、上記URLで内容は確認可能)。issues={review.get('issues')}")
        return

    print("[7/7] 最終バリデーション中...")
    errors = validate_script_and_images(script, image_paths)
    if errors:
        fail(post_id, f"最終バリデーションエラー: {errors}")
        sys.exit(1)

    caption = build_caption(script)
    db.update_post(post_id, status="ready")

    if dry_run:
        print("[DRY_RUN] Instagramへの投稿はスキップしました(画像は上記URLで確認できます)")
        print("--- caption ---")
        print(caption)
        return

    print("  Instagramへ投稿中...")
    try:
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
