"""
初回セットアップ専用スクリプト。
「Instagram API with Instagram Login」(Facebookページ連携不要の方式)で
IG_USER_ID / IG_ACCESS_TOKEN を取得するのを補助する。

事前にMeta for Developersで:
1. アプリを作成(タイプ: ビジネス)
2. 製品「Instagram API setup with Instagram business login」を追加
3. Instagramアプリの設定でリダイレクトURI(自社サイトの適当なURL等、httpsである必要あり)を登録
4. Instagram App ID / Instagram App Secret を控える
5. 対象のInstagramアカウント(leap_connect)をアプリのテスターとして追加し、
   Instagramアプリ側で招待を承認する

の準備をしてから、以下の手順で実行する。

--- 手順 ---
① まずこのスクリプトを引数なしで実行し、認可URLを表示する
   python scripts/setup_helper.py auth_url <APP_ID> <REDIRECT_URI>

② 表示されたURLをブラウザで開き、Instagramアカウントでログイン・許可する
   (leap_connectアカウント自身でログインすること)

③ 許可後にリダイレクトされたURLの ?code=xxxx の値をコピーする
   (末尾に #_ が付いていたら削除すること)

④ 以下を実行してトークンを取得する
   python scripts/setup_helper.py exchange <APP_ID> <APP_SECRET> <REDIRECT_URI> <CODE>

出力される IG_USER_ID と IG_ACCESS_TOKEN を GitHub Secrets に登録する。
"""
import sys
import urllib.parse

import requests

AUTH_BASE = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_BASE = "https://graph.instagram.com/v21.0"

SCOPES = "instagram_business_basic,instagram_business_content_publish"


def build_authorize_url(app_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
    }
    return f"{AUTH_BASE}?{urllib.parse.urlencode(params)}"


def exchange_code_for_short_token(app_id: str, app_secret: str, redirect_uri: str, code: str) -> dict:
    code = code.strip()
    if code.endswith("#_"):
        code = code[:-2]
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # {"access_token": ..., "user_id": ..., "permissions": [...]}


def exchange_for_long_lived_token(app_secret: str, short_token: str) -> dict:
    resp = requests.get(
        f"{GRAPH_BASE}/access_token",
        params={"grant_type": "ig_exchange_token", "client_secret": app_secret, "access_token": short_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # {"access_token": ..., "token_type": "bearer", "expires_in": 5184000}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "auth_url":
        if len(sys.argv) != 4:
            print("使い方: python scripts/setup_helper.py auth_url <APP_ID> <REDIRECT_URI>", file=sys.stderr)
            sys.exit(1)
        app_id, redirect_uri = sys.argv[2], sys.argv[3]
        print(build_authorize_url(app_id, redirect_uri))

    elif mode == "exchange":
        if len(sys.argv) != 6:
            print("使い方: python scripts/setup_helper.py exchange <APP_ID> <APP_SECRET> <REDIRECT_URI> <CODE>", file=sys.stderr)
            sys.exit(1)
        app_id, app_secret, redirect_uri, code = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]

        print("[1/2] 短期アクセストークンを取得中...")
        short = exchange_code_for_short_token(app_id, app_secret, redirect_uri, code)
        print(f"  user_id = {short.get('user_id')}")

        print("[2/2] 長期アクセストークン(60日)に交換中...")
        long_lived = exchange_for_long_lived_token(app_secret, short["access_token"])

        print("\n=== 結果(GitHub Secretsに登録してください) ===")
        print(f"IG_USER_ID       = {short.get('user_id')}")
        print(f"IG_ACCESS_TOKEN  = {long_lived['access_token']}")
        print(f"\n(有効期限: 約{long_lived.get('expires_in', 0) // 86400}日。期限が近づいたらscripts/refresh_token.pyで更新してください)")

    else:
        print(f"不明なモードです: {mode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
