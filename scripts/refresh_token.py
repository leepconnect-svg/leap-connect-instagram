"""
長期アクセストークン(60日)の有効期限が近づいたら実行して更新する。
既存のトークンが失効する"前"に実行する必要がある(失効後は再度setup_helper.pyからやり直し)。
"""
import os
import sys

import requests

GRAPH_BASE = "https://graph.instagram.com/v21.0"


def refresh_long_lived_token(current_access_token: str) -> dict:
    resp = requests.get(
        f"{GRAPH_BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": current_access_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    token = os.environ.get("IG_ACCESS_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not token:
        print("使い方: IG_ACCESS_TOKEN=xxx python scripts/refresh_token.py", file=sys.stderr)
        sys.exit(1)
    result = refresh_long_lived_token(token)
    print(f"新しいIG_ACCESS_TOKEN = {result['access_token']}")
    print(f"有効期限: 約{result.get('expires_in', 0) // 86400}日")
    print("GitHub Secretsの IG_ACCESS_TOKEN をこの値で更新してください。")
