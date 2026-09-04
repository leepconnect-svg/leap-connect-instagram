"""
ブランドデザインシステム(ネイビー×ホワイト×ゴールド)と、
6種類のレイアウトパターン(A/C/E/G/I/J)。投稿ごとにローテーションする。
未実装のB/D/F/H/K/Lは今後の拡張用にLAYOUT_RENDERERSへ追加していく想定。
"""
import os

from PIL import Image, ImageDraw, ImageFilter

from utils_image import cover_resize_crop
from utils_text import blend, fit_wrapped_text, font, wrap_text

WIDTH, HEIGHT = 1080, 1350
MARGIN = 72
FOOTER_H = 78

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
FONT_BLACK = os.path.join(FONT_DIR, "NotoSansCJKjp-Black.otf")
FONT_BOLD = os.path.join(FONT_DIR, "NotoSansCJKjp-Bold.otf")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoSansCJKjp-Regular.otf")

# --- ブランドカラー ---
NAVY = (13, 30, 56)
NAVY_MID = (22, 48, 86)
GOLD = (197, 160, 89)
OFFWHITE = (247, 245, 240)
TEXT_ON_LIGHT = (22, 26, 34)
TEXT_MUTED_LIGHT = (112, 110, 102)
TEXT_ON_DARK = (247, 245, 240)
TEXT_MUTED_DARK = (176, 184, 200)

ROLE_LABELS = {
    "hook": "導入",
    "why_problem": "問題提起",
    "cause": "原因",
    "risk": "リスク",
    "solution": "対策",
    "summary_cta": "まとめ",
}


def _f(path, size):
    return font(path, size)


def darken_photo(img: Image.Image, top_alpha: float, bottom_alpha: float) -> Image.Image:
    """写真の上下にネイビーのグラデーションスクリムを掛けて、文字を読みやすくする"""
    img = img.convert("RGB")
    overlay = Image.new("L", img.size)
    h = img.size[1]
    data = []
    for y in range(h):
        t = y / max(1, h - 1)
        a = top_alpha + (bottom_alpha - top_alpha) * t
        data.extend([int(255 * a)] * img.size[0])
    overlay.putdata(data)
    navy_layer = Image.new("RGB", img.size, NAVY)
    return Image.composite(navy_layer, img, overlay)


def _brand_mark(draw):
    draw.ellipse((MARGIN, 34, MARGIN + 10, 44), fill=GOLD)
    draw.text((MARGIN + 20, 26), "首都圏オーナー相談室", font=_f(FONT_BOLD, 22), fill=GOLD)


def _brand_mark_dark_bg(draw):
    draw.ellipse((MARGIN, 34, MARGIN + 10, 44), fill=GOLD)
    draw.text((MARGIN + 20, 26), "首都圏オーナー相談室", font=_f(FONT_BOLD, 22), fill=(*TEXT_ON_DARK,))


def _footer_bar(img: Image.Image, page_index: int, total_pages: int, brand_handle: str):
    draw = ImageDraw.Draw(img)
    y0 = HEIGHT - FOOTER_H
    draw.rectangle((0, y0, WIDTH, HEIGHT), fill=NAVY)
    draw.rectangle((0, y0, WIDTH, y0 + 3), fill=GOLD)
    draw.text((MARGIN, y0 + 24), brand_handle, font=_f(FONT_BOLD, 26), fill=(*TEXT_ON_DARK,))
    counter = f"{page_index + 1} / {total_pages}"
    cbbox = draw.textbbox((0, 0), counter, font=_f(FONT_REGULAR, 24))
    cw = cbbox[2] - cbbox[0]
    draw.text((WIDTH - MARGIN - cw, y0 + 26), counter, font=_f(FONT_REGULAR, 24), fill=(*TEXT_MUTED_DARK,))
    return draw


def _role_tag(draw, text, x, y, dark_bg=False):
    tag_font = _f(FONT_BOLD, 26)
    bbox = draw.textbbox((0, 0), text, font=tag_font)
    w = bbox[2] - bbox[0]
    pad_x, pad_y = 22, 12
    box = (x, y, x + w + pad_x * 2, y + 26 + pad_y * 2)
    draw.rounded_rectangle(box, radius=999, fill=GOLD)
    draw.text((x + pad_x, y + pad_y - 2), text, font=tag_font, fill=NAVY)
    return box[3] - box[1]


def _load_photo(photo_path: str | None) -> Image.Image | None:
    if not photo_path or not os.path.exists(photo_path):
        return None
    return Image.open(photo_path).convert("RGB")


# ============================================================ Layout A ====
def render_A(slide, index, total, photo_path, brand_handle):
    """大見出し＋写真: 上部フルブリード写真＋下部ネイビーパネルに見出し(縦中央寄せ)"""
    photo = _load_photo(photo_path)
    photo_h = int(HEIGHT * 0.56)
    img = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    if photo:
        p = cover_resize_crop(photo, WIDTH, photo_h)
        p = darken_photo(p, 0.22, 0.58)
        img.paste(p, (0, 0))
    draw = ImageDraw.Draw(img)

    panel_top = photo_h
    draw.rectangle((0, panel_top, WIDTH, HEIGHT - FOOTER_H), fill=NAVY)
    draw.rectangle((0, panel_top, WIDTH, panel_top + 4), fill=GOLD)

    max_w = WIDTH - MARGIN * 2
    has_tag = slide.get("role") in ROLE_LABELS and index != 0
    tag_h = 78 if has_tag else 0

    max_size = 64 if index == 0 else 52
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, max_size, 34, 3)
    line_h = int(h_font.size * 1.3)
    heading_h = line_h * len(h_lines)

    body_h = 0
    b_font, b_lines = None, []
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_REGULAR, max_w, 34, 24, 4)
        body_h = int(b_font.size * 1.55) * len(b_lines)

    gap1, gap2 = 26, 24
    block_h = tag_h + heading_h + (gap2 + body_h if body_h else 0)
    safe_top, safe_bottom = panel_top + 30, HEIGHT - FOOTER_H - 30
    y = safe_top + max(0, (safe_bottom - safe_top - block_h) / 2)

    if has_tag:
        _role_tag(draw, ROLE_LABELS[slide["role"]], MARGIN, y, dark_bg=True)
        y += tag_h + gap1 - 26

    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_DARK,))
        y += line_h

    if body_h:
        y += gap2
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(*TEXT_MUTED_DARK,))
            y += int(b_font.size * 1.55)

    _footer_bar(img, index, total, brand_handle)
    return img


# ============================================================ Layout C ====
def render_C(slide, index, total, photo_path, brand_handle):
    """チェックリスト: オフホワイト背景＋チェックアイコン＋見出し／本文、上部にミニ進捗チェック"""
    img = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw)

    # ミニ進捗(6個の丸チェック)
    dot_r = 14
    gap = 40
    start_x = WIDTH / 2 - (total - 1) * gap / 2
    for i in range(total):
        cx = start_x + i * gap
        cy = 96
        if i < index:
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=GOLD)
            draw.line((cx - 6, cy, cx - 2, cy + 6), fill=NAVY, width=3)
            draw.line((cx - 2, cy + 6, cx + 7, cy - 6), fill=NAVY, width=3)
        elif i == index:
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), outline=GOLD, width=4)
        else:
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), outline=(210, 205, 195), width=3)

    # 右下に写真サムネイル(装飾)
    photo = _load_photo(photo_path)
    thumb_size = 260
    if photo:
        thumb = cover_resize_crop(photo, thumb_size, thumb_size)
        mask = Image.new("L", (thumb_size, thumb_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, thumb_size, thumb_size), radius=24, fill=255)
        canvas = Image.new("RGB", (thumb_size, thumb_size), OFFWHITE)
        canvas.paste(thumb, (0, 0), mask)
        tx, ty = WIDTH - MARGIN - thumb_size, HEIGHT - FOOTER_H - 40 - thumb_size
        img.paste(canvas, (tx, ty), mask)
        draw.rounded_rectangle((tx, ty, tx + thumb_size, ty + thumb_size), radius=24, outline=GOLD, width=4)

    # --- 1st pass: 高さ測定 ---
    box_size = 84
    max_w = WIDTH - MARGIN * 2 - (thumb_size + 40 if photo else 0)
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 62, 40, 2)
    heading_h = int(h_font.size * 1.3) * len(h_lines)

    b_font, b_lines = (None, [])
    body_h = 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_REGULAR, max_w, 42, 30, 5)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    gap1, gap2, divider_h = 44, 44, 7
    block_h = box_size + gap1 + heading_h + gap2 + divider_h + (44 + body_h if body_h else 0)

    safe_top, safe_bottom = 190, HEIGHT - FOOTER_H - 40
    y = safe_top + max(0, (safe_bottom - safe_top - block_h) / 2)

    # --- 2nd pass: 描画 ---
    draw.rounded_rectangle((MARGIN, y, MARGIN + box_size, y + box_size), radius=16, outline=GOLD, width=6)
    draw.line((MARGIN + 20, y + 44, MARGIN + 36, y + 62), fill=GOLD, width=8)
    draw.line((MARGIN + 36, y + 62, MARGIN + 66, y + 22), fill=GOLD, width=8)
    y += box_size + gap1

    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_LIGHT,))
        y += int(h_font.size * 1.3)
    y += gap2 - 34

    draw.rounded_rectangle((MARGIN, y, MARGIN + 90, y + divider_h), radius=4, fill=GOLD)
    y += divider_h + 44

    if body_h:
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(60, 58, 52))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle)
    return img


# ============================================================ Layout E ====
def render_E(slide, index, total, photo_path, brand_handle):
    """問題→原因→対策: 役割タグを大きく見せるフロー訴求型。右側に写真、左に文字ブロックを縦中央で揃える"""
    img = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw)

    photo = _load_photo(photo_path)
    thumb_w, thumb_h = (320, 420) if photo else (0, 0)
    text_max_w = WIDTH - MARGIN * 2 - (thumb_w + 40 if photo else 0)

    role_label = ROLE_LABELS.get(slide.get("role"), "")
    tag_h = 78 if role_label else 0

    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, text_max_w, 58, 36, 3)
    heading_h = int(h_font.size * 1.3) * len(h_lines)

    b_font, b_lines, body_h = None, [], 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_REGULAR, text_max_w, 40, 28, 6)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    divider_h, gap_after_tag, gap_after_head, gap_after_div = 7, 26, 18, 40
    text_block_h = tag_h + gap_after_tag * (1 if tag_h else 0) + heading_h + gap_after_head + divider_h + (gap_after_div + body_h if body_h else 0)

    safe_top, safe_bottom = 150, HEIGHT - FOOTER_H - 40
    center_y = safe_top + (safe_bottom - safe_top) / 2

    y = center_y - text_block_h / 2
    if role_label:
        _role_tag(draw, role_label, MARGIN, y)
        y += tag_h + gap_after_tag

    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_LIGHT,))
        y += int(h_font.size * 1.3)
    y += gap_after_head

    draw.rounded_rectangle((MARGIN, y, MARGIN + 90, y + divider_h), radius=4, fill=GOLD)
    y += divider_h

    if body_h:
        y += gap_after_div
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(60, 58, 52))
            y += int(b_font.size * 1.6)

    if photo:
        p = cover_resize_crop(photo, thumb_w, thumb_h)
        py = center_y - thumb_h / 2
        img.paste(p, (WIDTH - MARGIN - thumb_w, int(py)))
        draw.rectangle((WIDTH - MARGIN - thumb_w, int(py), WIDTH - MARGIN, int(py) + thumb_h), outline=GOLD, width=4)

    _footer_bar(img, index, total, brand_handle)
    return img


# ============================================================ Layout G ====
def render_G(slide, index, total, photo_path, brand_handle):
    """ランキング/数字強調: 大きな番号バッジ＋見出し／本文"""
    img = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw)

    # 右下に写真サムネイル(装飾)
    photo = _load_photo(photo_path)
    thumb_size = 240
    if photo:
        thumb = cover_resize_crop(photo, thumb_size, thumb_size)
        mask = Image.new("L", (thumb_size, thumb_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, thumb_size, thumb_size), fill=255)
        canvas = Image.new("RGB", (thumb_size, thumb_size), OFFWHITE)
        canvas.paste(thumb, (0, 0), mask)
        tx, ty = WIDTH - MARGIN - thumb_size, HEIGHT - FOOTER_H - 50 - thumb_size
        img.paste(canvas, (tx, ty), mask)
        draw.ellipse((tx, ty, tx + thumb_size, ty + thumb_size), outline=GOLD, width=4)

    badge_r = 90
    max_w = WIDTH - MARGIN * 2

    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 64, 40, 2)
    heading_h = int(h_font.size * 1.3) * len(h_lines)

    b_font, b_lines, body_h = None, [], 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_REGULAR, max_w, 42, 30, 5)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    gap1, gap2, divider_h = 50, 44, 7
    block_h = badge_r * 2 + gap1 + heading_h + gap2 + divider_h + (44 + body_h if body_h else 0)
    safe_top, safe_bottom = 150, HEIGHT - FOOTER_H - 40
    y = safe_top + max(0, (safe_bottom - safe_top - block_h) / 2)

    badge_cx, badge_cy = MARGIN + badge_r, y + badge_r
    draw.ellipse((badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r), fill=NAVY)
    draw.ellipse((badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r), outline=GOLD, width=5)
    num_font = _f(FONT_BLACK, 88)
    num_text = str(index + 1) if slide.get("role") not in ("hook", "summary_cta") else ("Q" if slide.get("role") == "hook" else "✓")
    nbbox = draw.textbbox((0, 0), num_text, font=num_font)
    nw, nh = nbbox[2] - nbbox[0], nbbox[3] - nbbox[1]
    draw.text((badge_cx - nw / 2 - nbbox[0], badge_cy - nh / 2 - nbbox[1]), num_text, font=num_font, fill=GOLD)

    label = f"{index + 1} / {total}"
    draw.text((badge_cx + badge_r + 28, badge_cy - 14), label, font=_f(FONT_BOLD, 26), fill=TEXT_MUTED_LIGHT)

    y += badge_r * 2 + gap1
    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_LIGHT,))
        y += int(h_font.size * 1.3)
    y += gap2 - 34

    draw.rounded_rectangle((MARGIN, y, MARGIN + 90, y + divider_h), radius=4, fill=GOLD)
    y += divider_h + 44

    if body_h:
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(60, 58, 52))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle)
    return img


# ============================================================ Layout I ====
def render_I(slide, index, total, photo_path, brand_handle):
    """写真全面＋短文: エディトリアル/雑誌風。見出しのみ、本文なし"""
    photo = _load_photo(photo_path)
    img = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    if photo:
        p = cover_resize_crop(photo, WIDTH, HEIGHT)
        p = darken_photo(p, 0.24, 0.75)
        img.paste(p, (0, 0))
    draw = ImageDraw.Draw(img)
    _brand_mark_dark_bg(draw)

    max_w = WIDTH - MARGIN * 2
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 76, 44, 3)
    line_h = int(h_font.size * 1.3)
    total_h = line_h * len(h_lines)
    y = HEIGHT - FOOTER_H - 60 - total_h
    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_DARK,))
        y += line_h

    _footer_bar(img, index, total, brand_handle)
    return img


# ============================================================ Layout J ====
def render_J(slide, index, total, photo_path, brand_handle):
    """カード型: オフホワイト背景に角丸写真カード＋下にテキスト"""
    img = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw)

    photo = _load_photo(photo_path)
    card_top, card_h = 110, 480
    if photo:
        p = cover_resize_crop(photo, WIDTH - MARGIN * 2, card_h)
        mask = Image.new("L", p.size, 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle((0, 0, p.size[0], p.size[1]), radius=28, fill=255)
        card_img = Image.new("RGB", p.size, OFFWHITE)
        card_img.paste(p, (0, 0), mask)
        img.paste(card_img, (MARGIN, card_top), mask)
        draw.rounded_rectangle((MARGIN, card_top, WIDTH - MARGIN, card_top + card_h), radius=28, outline=GOLD, width=4)

    max_w = WIDTH - MARGIN * 2
    y = card_top + card_h + 50
    if slide.get("role") in ROLE_LABELS and slide.get("role") != "hook":
        _role_tag(draw, ROLE_LABELS[slide["role"]], MARGIN, y)
        y += 78

    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 58, 36, 2)
    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_LIGHT,))
        y += int(h_font.size * 1.3)

    if slide.get("body"):
        y += 10
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_REGULAR, max_w, 36, 26, 3)
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(60, 58, 52))
            y += int(b_font.size * 1.55)

    _footer_bar(img, index, total, brand_handle)
    return img


LAYOUT_RENDERERS = {
    "A": render_A,
    "C": render_C,
    "E": render_E,
    "G": render_G,
    "I": render_I,
    "J": render_J,
}


def render_slide(layout_type: str, slide: dict, index: int, total: int, photo_path: str | None, brand_handle: str) -> Image.Image:
    renderer = LAYOUT_RENDERERS.get(layout_type)
    if renderer is None:
        raise ValueError(f"未実装のレイアウトです: {layout_type}")
    return renderer(slide, index, total, photo_path, brand_handle)
