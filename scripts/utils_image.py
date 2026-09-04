"""共通の画像処理ユーティリティ"""
from PIL import Image


def cover_resize_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """アスペクト比が違う画像を、指定サイズに"cover"方式(はみ出た分を中央基準でクロップ)でリサイズする"""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # 元画像の方が横長 → 高さを基準に拡大し、左右をクロップ
        new_h = target_h
        new_w = int(src_w * (target_h / src_h))
    else:
        # 元画像の方が縦長 → 幅を基準に拡大し、上下をクロップ
        new_w = target_w
        new_h = int(src_h * (target_w / src_w))

    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))
