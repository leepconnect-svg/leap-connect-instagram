"""
ImgBB (無料の画像アップロードAPI) にPNGをアップロードし、
Instagram APIが読める公開URLを取得する。
https://api.imgbb.com/ で無料APIキーを取得して使う。
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

IMGBB_URL = "https://api.imgbb.com/1/upload"


def upload_image(api_key: str, image_path: str, expiration_seconds: int = 0) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    form = {"key": api_key, "image": b64}
    if expiration_seconds:
        form["expiration"] = str(expiration_seconds)

    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(IMGBB_URL, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"ImgBB upload error {e.code}: {body}") from e

    if not result.get("success"):
        raise RuntimeError(f"ImgBB upload failed: {result}")

    return result["data"]["url"]


def upload_images(api_key: str, image_paths: list[str]) -> list[str]:
    return [upload_image(api_key, p) for p in image_paths]


if __name__ == "__main__":
    api_key = os.environ.get("IMGBB_API_KEY")
    if not api_key or len(sys.argv) < 2:
        print("使い方: IMGBB_API_KEY=xxx python upload_image.py <image_path>", file=sys.stderr)
        sys.exit(1)
    print(upload_image(api_key, sys.argv[1]))
