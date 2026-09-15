"""
品質ゲート(80点未満)で自動投稿が見送られた投稿を、オーナーが実際の画像を
目視確認した上で「この内容のまま投稿してほしい」と明示的に指示した場合に、
再生成せずそのままInstagramへ投稿するための一回限りの手動スクリプト。

通常の自動パイプライン(main.py)は経由しない。画像はすでに
publish_images_to_github() でリポジトリにコミット済み(jsdelivr配信中)である
前提で、そのURLをそのまま使う。

使い方: 環境変数 REPOST_POST_ID に db/leapconnect.sqlite3 の posts.id を入れて実行。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import db
from post_instagram import post_carousel
from publish_images import _get_branch, _get_repo_slug

ROOT = os.path.join(os.path.dirname(__file__), "..")


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


def local_paths_to_jsdelivr(image_paths: list[str], repo_root: str) -> list[str]:
    """DBに保存されたローカル/CI環境の絶対パスから、リポジトリ相対パスを取り出し
    jsdelivr URLに変換する(publish_images.pyと同じURL形式)"""
    repo_slug = _get_repo_slug(repo_root)
    branch = _get_branch(repo_root)
    urls = []
    for p in image_paths:
        norm = p.replace("\\", "/")
        idx = norm.find("data/generated/")
        if idx < 0:
            raise RuntimeError(f"data/generated/ 以下のパスが見つかりません: {p}")
        rel = norm[idx:]
        urls.append(f"https://cdn.jsdelivr.net/gh/{repo_slug}@{branch}/{rel}")
    return urls


def build_caption(caption: str, hashtags: list[str]) -> str:
    return f"{caption}\n.\n.\n.\n{' '.join(hashtags)}"


def main():
    post_id = os.environ.get("REPOST_POST_ID")
    if not post_id:
        print("[ERROR] REPOST_POST_ID が未設定です", file=sys.stderr)
        sys.exit(1)
    env = require_env("IG_USER_ID", "IG_ACCESS_TOKEN")

    db.init_db()
    post = db.get_post(post_id)
    if not post:
        print(f"[ERROR] post_id={post_id} がDBに見つかりません", file=sys.stderr)
        sys.exit(1)
    if post.get("status") == "posted":
        print(f"[ERROR] post_id={post_id} は既に投稿済みです(ig_media_id={post.get('ig_media_id')})", file=sys.stderr)
        sys.exit(1)

    image_paths = json.loads(post["image_paths"])
    hashtags = json.loads(post["hashtags"])
    image_urls = local_paths_to_jsdelivr(image_paths, ROOT)
    caption = build_caption(post["caption"], hashtags)

    print(f"  post_id = {post_id}")
    print(f"  title = {post['title']}")
    print(f"  quality_score = {post.get('quality_score')} (手動承認により投稿)")
    print("  image_urls:")
    for u in image_urls:
        print(f"    {u}")

    media_id = post_carousel(env["IG_USER_ID"], env["IG_ACCESS_TOKEN"], image_urls, caption)
    db.update_post(post_id, status="posted", ig_media_id=media_id, posted_at=db.now_iso(),
                    reject_reason=None)
    print(f"  公開しました: media_id={media_id}")


if __name__ == "__main__":
    main()
