"""
STEP 7 (フェーズ3): 投稿済みメディアのインサイトを取得してDBへ保存する。
投稿から一定時間(デフォルト24時間)経過したものを対象にする。

注意: Instagram Graph APIのメディア単位インサイトで直接取得できるのは
reach/saved/likes/comments/shares/total_interactions程度。
profile_visits(プロフィールアクセス)やnew_followers(フォロワー増加)は
アカウント単位の集計値であり、個別投稿に厳密に紐付けることは公式APIの範囲では出来ない。
これらは現状NULLのまま保存し、必要であればInstagramアプリの「インサイト」画面を見て
手動でDBに記録する運用を想定する(将来的な拡張ポイント)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import db
from post_instagram import InstagramAPIError, get_media_insights

MEDIA_METRICS_FULL = ["reach", "saved", "likes", "comments", "shares", "total_interactions"]
MEDIA_METRICS_FALLBACK = ["reach", "saved", "likes", "comments"]


def fetch_and_store_insights(ig_access_token: str, older_than_hours: int = 24, limit: int = 30) -> list[dict]:
    posts = db.get_posts_pending_insights(older_than_hours=older_than_hours, limit=limit)
    results = []

    for post in posts:
        media_id = post.get("ig_media_id")
        if not media_id:
            continue

        try:
            insights = get_media_insights(media_id, ig_access_token, MEDIA_METRICS_FULL)
        except InstagramAPIError:
            try:
                insights = get_media_insights(media_id, ig_access_token, MEDIA_METRICS_FALLBACK)
            except InstagramAPIError as e:
                print(f"[WARN] インサイト取得失敗 post_id={post['id']}: {e}", file=sys.stderr)
                continue

        update_fields = {
            "reach": insights.get("reach"),
            "likes": insights.get("likes"),
            "saves": insights.get("saved"),
            "shares": insights.get("shares"),
            "comments": insights.get("comments"),
            "insights_fetched_at": db.now_iso(),
        }
        db.update_post(post["id"], **update_fields)
        results.append({"post_id": post["id"], **update_fields})
        print(f"[OK] {post['id']}: reach={update_fields['reach']} saves={update_fields['saves']} shares={update_fields['shares']}")

    return results


if __name__ == "__main__":
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        print("IG_ACCESS_TOKEN が未設定です", file=sys.stderr)
        sys.exit(1)
    fetch_and_store_insights(token)
