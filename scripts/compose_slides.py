"""
STEP 4: 台本(script) + 生成済み背景写真(raw_photo_paths)から、
ブランドデザインを適用した6枚の投稿用画像(1080x1350)を書き出す。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from layouts import render_slide


def compose_slides(script: dict, raw_photo_paths: list[str], out_dir: str, brand_handle: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    slides = script["slides"]
    layout_type = script["layout_type"]
    total = len(slides)

    paths = []
    for i, slide in enumerate(slides):
        photo_path = raw_photo_paths[i] if i < len(raw_photo_paths) else None
        img = render_slide(layout_type, slide, i, total, photo_path, brand_handle)
        path = os.path.join(out_dir, f"slide_{i:02d}.png")
        img.save(path)
        paths.append(path)

    return paths


if __name__ == "__main__":
    sample_script = {
        "layout_type": "C",
        "slides": [
            {"role": "hook", "heading": "その空室、放置していませんか？", "body": ""},
            {"role": "why_problem", "heading": "空室が長引く部屋の共通点", "body": "実は「見た目」より先に見られているポイントがあります。"},
            {"role": "cause", "heading": "写真と現地の印象の差", "body": "内見前の期待値と現地のギャップが、決定率を大きく左右します。"},
            {"role": "risk", "heading": "放置すると起こること", "body": "空室期間が延びるほど、賃料収入の減少と募集コストの増加につながります。"},
            {"role": "solution", "heading": "確認したい3つの視点", "body": "写真・共用部の清潔感・募集条件のバランスを見直すことが第一歩です。"},
            {"role": "summary_cta", "heading": "まとめ", "body": "気になる方は保存して、あとで見返してみてください。"},
        ],
    }
    out = compose_slides(sample_script, raw_photo_paths=[], out_dir=os.path.join(os.path.dirname(__file__), "..", "output", "preview_C"), brand_handle="@leap_connect")
    print("\n".join(out))
