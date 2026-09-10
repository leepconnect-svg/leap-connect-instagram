"""
STEP 6: Instagram API with Instagram Login (Facebookページ連携不要の新方式)で
カルーセル投稿を行う。

事前条件:
- Instagramがビジネス/クリエイターアカウント
- Meta for Developersアプリで「Instagram API setup with Instagram business login」製品を追加し、
  instagram_business_basic / instagram_business_content_publish 権限で取得した
  長期アクセストークン(IG_ACCESS_TOKEN)とIGユーザーID(IG_USER_ID)を取得済み
  (取得手順はREADME.md参照。scripts/setup_helper.pyで取得を補助)

Facebookページとの連携は不要。エンドポイントは graph.instagram.com を使う
(従来のgraph.facebook.comとは別のホスト)。

処理の流れ:
1. 各画像URLについて is_carousel_item=true でメディアコンテナを作成
2. media_type=CAROUSEL, children=[...] でカルーセル全体のコンテナを作成
3. media_publish で公開
"""
import os
import sys
import time
import requests

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.instagram.com/{GRAPH_VERSION}"


class InstagramAPIError(RuntimeError):
    pass


def _check(resp: requests.Response):
    if resp.status_code >= 400:
        raise InstagramAPIError(f"Instagram API error {resp.status_code}: {resp.text}")
    return resp.json()


def create_carousel_item(ig_user_id: str, access_token: str, image_url: str, max_retries: int = 3) -> str:
    """画像URLからカルーセル用メディアコンテナを作成する。

    アップロード直後の画像は、ホスティング側のCDN伝播が間に合わず
    Instagram側の取得が一時的に失敗することがある
    ("Media download has failed. The media URI doesn't meet our requirements.")。
    そのため失敗時は待機してリトライする。
    """
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(5 * attempt)  # 5s, 10s, ... と待機を伸ばす
        resp = requests.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            data={"image_url": image_url, "is_carousel_item": "true", "access_token": access_token},
            timeout=60,
        )
        try:
            return _check(resp)["id"]
        except InstagramAPIError as e:
            last_error = e
            if "could not be fetched" in str(e) or "Media download has failed" in str(e):
                continue  # 取得失敗はリトライ対象
            raise  # それ以外のエラーは即座に失敗させる
    raise last_error


def wait_until_ready(container_id: str, access_token: str, timeout_sec: int = 150) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        data = _check(resp)
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise InstagramAPIError(f"メディア処理エラー: container_id={container_id}")
        time.sleep(3)
    raise InstagramAPIError(f"メディア処理がタイムアウトしました: container_id={container_id}")


def create_carousel_container(ig_user_id: str, access_token: str, children_ids: list[str], caption: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=60,
    )
    return _check(resp)["id"]


def publish_container(ig_user_id: str, access_token: str, container_id: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    return _check(resp)["id"]


def post_carousel(ig_user_id: str, access_token: str, image_urls: list[str], caption: str) -> str:
    if not (2 <= len(image_urls) <= 10):
        raise ValueError("カルーセルは2〜10枚である必要があります")

    children_ids = []
    for url in image_urls:
        item_id = create_carousel_item(ig_user_id, access_token, url)
        wait_until_ready(item_id, access_token)
        children_ids.append(item_id)

    container_id = create_carousel_container(ig_user_id, access_token, children_ids, caption)
    wait_until_ready(container_id, access_token)

    return publish_container(ig_user_id, access_token, container_id)


def get_media_insights(media_id: str, access_token: str, metrics: list[str]) -> dict:
    """投稿済みメディアのインサイトを取得(STEP 7で使用)"""
    resp = requests.get(
        f"{GRAPH_BASE}/{media_id}/insights",
        params={"metric": ",".join(metrics), "access_token": access_token},
        timeout=30,
    )
    data = _check(resp)
    result = {}
    for item in data.get("data", []):
        values = item.get("values", [])
        result[item["name"]] = values[0]["value"] if values else None
    return result


if __name__ == "__main__":
    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")
    if not ig_user_id or not access_token or len(sys.argv) < 2:
        print("使い方: IG_USER_ID=xxx IG_ACCESS_TOKEN=xxx python post_instagram.py <url1> <url2> ...", file=sys.stderr)
        sys.exit(1)
    media_id = post_carousel(ig_user_id, access_token, sys.argv[1:], caption="テスト投稿")
    print(f"公開しました: media_id={media_id}")
