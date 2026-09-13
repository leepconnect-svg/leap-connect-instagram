"""
ブランドデザインシステムと、6種類のレイアウトパターン(A/C/E/G/I/J)。投稿ごとにローテーションする。
未実装のB/D/F/H/K/Lは今後の拡張用にLAYOUT_RENDERERSへ追加していく想定。

【デザイン方針(v2)】
実際のleap_connectアカウントの過去投稿(人が作成)を確認したところ、
・写真を画面いっぱいに大きく使う
・強調語に黄色マーカー風のハイライト
・カラフルなアイコンバッジ
という、AIの初期版よりずっとエネルギッシュな「雑誌広告/SNS広告」的スタイルだった。
v2ではこれに合わせ、全レイアウトで写真をフルブリード(全面)背景として使い、
投稿ごとに鮮やかなアクセントカラーをローテーションする方式に変更する。
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

# --- ベースのブランドカラー ---
NAVY = (12, 20, 38)
OFFWHITE = (250, 248, 244)
TEXT_ON_LIGHT = (22, 26, 34)
TEXT_MUTED_LIGHT = (112, 110, 102)
TEXT_ON_DARK = (250, 248, 244)
TEXT_MUTED_DARK = (198, 204, 218)
WHITE = (255, 255, 255)

# 投稿ごとにローテーションする鮮やかなアクセントカラー(実際の過去投稿の
# 「黄色マーカー」「カラフルバッジ」に寄せた、視認性の高いビビッドカラー)
ACCENT_PALETTE = [
    (255, 199, 42),   # ビビッドイエロー(マーカー風)
    (255, 122, 89),   # コーラルオレンジ
    (255, 214, 10),   # ゴールドイエロー
    (110, 231, 183),  # ミント/ティール
    (255, 138, 0),    # ディープオレンジ
]

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


def pick_accent(seed: int):
    return ACCENT_PALETTE[seed % len(ACCENT_PALETTE)]


def darken_photo(img: Image.Image, top_alpha: float, bottom_alpha: float, base=NAVY) -> Image.Image:
    """写真の上下にグラデーションスクリムを掛けて、文字を読みやすくする"""
    img = img.convert("RGB")
    overlay = Image.new("L", img.size)
    h = img.size[1]
    data = []
    for y in range(h):
        t = y / max(1, h - 1)
        a = top_alpha + (bottom_alpha - top_alpha) * t
        data.extend([int(255 * a)] * img.size[0])
    overlay.putdata(data)
    dark_layer = Image.new("RGB", img.size, base)
    return Image.composite(dark_layer, img, overlay)


def full_bleed_bg(photo_path: str | None, top_alpha=0.30, bottom_alpha=0.80) -> Image.Image:
    """写真をフルブリードで敷き、上下にスクリムをかけたベース画像を作る(写真がなければ濃紺の単色)"""
    photo = _load_photo(photo_path)
    if photo:
        p = cover_resize_crop(photo, WIDTH, HEIGHT)
        return darken_photo(p, top_alpha, bottom_alpha)
    return Image.new("RGB", (WIDTH, HEIGHT), NAVY)


def _brand_mark(draw, accent, on_dark=True):
    color = accent
    text_color = TEXT_ON_DARK if on_dark else TEXT_ON_LIGHT
    draw.ellipse((MARGIN, 34, MARGIN + 12, 46), fill=color)
    draw.text((MARGIN + 22, 26), "首都圏オーナー相談室", font=_f(FONT_BOLD, 22), fill=text_color)


def _footer_bar(img: Image.Image, page_index: int, total_pages: int, brand_handle: str, accent):
    draw = ImageDraw.Draw(img)
    y0 = HEIGHT - FOOTER_H
    draw.rectangle((0, y0, WIDTH, HEIGHT), fill=NAVY)
    draw.rectangle((0, y0, WIDTH, y0 + 4), fill=accent)
    draw.text((MARGIN, y0 + 24), brand_handle, font=_f(FONT_BOLD, 26), fill=(*TEXT_ON_DARK,))
    counter = f"{page_index + 1} / {total_pages}"
    cbbox = draw.textbbox((0, 0), counter, font=_f(FONT_REGULAR, 24))
    cw = cbbox[2] - cbbox[0]
    draw.text((WIDTH - MARGIN - cw, y0 + 26), counter, font=_f(FONT_REGULAR, 24), fill=(*TEXT_MUTED_DARK,))
    return draw


def _pill_badge(draw, text, x, y, accent, text_color=None, font_size=28):
    tag_font = _f(FONT_BOLD, font_size)
    bbox = draw.textbbox((0, 0), text, font=tag_font)
    w = bbox[2] - bbox[0]
    pad_x, pad_y = 24, 13
    box = (x, y, x + w + pad_x * 2, y + font_size + pad_y * 2)
    draw.rounded_rectangle(box, radius=999, fill=accent)
    draw.text((x + pad_x, y + pad_y - 2), text, font=tag_font, fill=text_color or NAVY)
    return box[3] - box[1]


def _highlight_lines(draw, lines, font_obj, center_x, start_y, line_height, accent, text_color=WHITE, highlight_all=True):
    """各行の背景に太いマーカー風ハイライトを敷いてから白文字を乗せる(中央揃え)"""
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        w = bbox[2] - bbox[0]
        if highlight_all:
            pad_x, pad_y = 16, 8
            box = (center_x - w / 2 - pad_x, y + bbox[1] - pad_y, center_x + w / 2 + pad_x, y + bbox[3] + pad_y)
            draw.rectangle(box, fill=accent)
            draw.text((center_x - w / 2, y), line, font=font_obj, fill=NAVY)
        else:
            draw.text((center_x - w / 2, y), line, font=font_obj, fill=text_color)
        y += line_height
    return y


def _load_photo(photo_path: str | None) -> Image.Image | None:
    if not photo_path or not os.path.exists(photo_path):
        return None
    return Image.open(photo_path).convert("RGB")


# ============================================================ Layout A ====
def render_A(slide, index, total, photo_path, brand_handle, accent):
    """フルブリード写真＋下部に黄色マーカー見出し。1枚目の主力レイアウト"""
    img = full_bleed_bg(photo_path, top_alpha=0.15, bottom_alpha=0.82)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent)

    max_w = WIDTH - MARGIN * 2
    has_tag = slide.get("role") in ROLE_LABELS and index != 0

    max_size = 66 if index == 0 else 56
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w - 40, max_size, 36, 3)
    line_h = int(h_font.size * 1.42)
    heading_h = line_h * len(h_lines)

    body_h = 0
    b_font, b_lines = None, []
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_BOLD, max_w, 34, 24, 4)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    tag_h = 74 if has_tag else 0
    gap_tag, gap_body = 30, 26
    block_h = tag_h + (gap_tag if has_tag else 0) + heading_h + (gap_body + body_h if body_h else 0)
    bottom_limit = HEIGHT - FOOTER_H - 50
    y = bottom_limit - block_h

    if has_tag:
        _pill_badge(draw, ROLE_LABELS[slide["role"]], MARGIN, y, accent)
        y += tag_h + gap_tag

    y = _highlight_lines(draw, h_lines, h_font, WIDTH / 2, y, line_h, accent)

    if body_h:
        y += gap_body
        for line in b_lines:
            bbox = draw.textbbox((0, 0), line, font=b_font)
            w = bbox[2] - bbox[0]
            draw.text((WIDTH / 2 - w / 2, y), line, font=b_font, fill=(*TEXT_ON_DARK,))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


# ============================================================ Layout C ====
def render_C(slide, index, total, photo_path, brand_handle, accent):
    """チェックリスト: フルブリード写真＋大きなチェックアイコン＋中央下部にテキスト"""
    img = full_bleed_bg(photo_path, top_alpha=0.35, bottom_alpha=0.88)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent)

    # 上部にミニ進捗(6個の丸チェック)
    dot_r = 13
    gap = 38
    start_x = WIDTH / 2 - (total - 1) * gap / 2
    for i in range(total):
        cx = start_x + i * gap
        cy = 96
        if i <= index:
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=accent)
            if i < index:
                draw.line((cx - 5, cy, cx - 1, cy + 5), fill=NAVY, width=3)
                draw.line((cx - 1, cy + 5, cx + 6, cy - 5), fill=NAVY, width=3)
        else:
            draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), outline=(255, 255, 255), width=3)

    max_w = WIDTH - MARGIN * 2
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 66, 42, 2)
    heading_h = int(h_font.size * 1.35) * len(h_lines)

    b_font, b_lines, body_h = None, [], 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_BOLD, max_w, 38, 28, 4)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    box_size = 96
    gap1, gap2 = 34, 30
    block_h = box_size + gap1 + heading_h + (gap2 + body_h if body_h else 0)
    bottom_limit = HEIGHT - FOOTER_H - 56
    y = bottom_limit - block_h

    # 大きな丸背景付きチェックアイコン(中央)
    icon_cx = WIDTH / 2
    draw.ellipse((icon_cx - box_size / 2, y, icon_cx + box_size / 2, y + box_size), fill=accent)
    draw.line((icon_cx - 22, y + 50, icon_cx - 6, y + 68), fill=NAVY, width=10)
    draw.line((icon_cx - 6, y + 68, icon_cx + 28, y + 26), fill=NAVY, width=10)
    y += box_size + gap1

    y = _highlight_lines(draw, h_lines, h_font, WIDTH / 2, y, int(h_font.size * 1.35), accent)

    if body_h:
        y += gap2
        for line in b_lines:
            bbox = draw.textbbox((0, 0), line, font=b_font)
            w = bbox[2] - bbox[0]
            draw.text((WIDTH / 2 - w / 2, y), line, font=b_font, fill=(*TEXT_ON_DARK,))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


# ============================================================ Layout E ====
def render_E(slide, index, total, photo_path, brand_handle, accent):
    """問題→原因→対策: フルブリード写真＋役割バッジ＋左下寄せの太字見出し"""
    img = full_bleed_bg(photo_path, top_alpha=0.10, bottom_alpha=0.85)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent)

    role_label = ROLE_LABELS.get(slide.get("role"), "")
    max_w = WIDTH - MARGIN * 2

    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 60, 38, 3)
    heading_h = int(h_font.size * 1.35) * len(h_lines)

    b_font, b_lines, body_h = None, [], 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_BOLD, max_w, 36, 26, 5)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    tag_h = 74 if role_label else 0
    gap_tag, gap_body = 26, 28
    block_h = tag_h + heading_h + (gap_body + body_h if body_h else 0)
    y = HEIGHT - FOOTER_H - 56 - block_h

    if role_label:
        _pill_badge(draw, role_label, MARGIN, y, accent)
        y += tag_h + gap_tag - 26

    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_DARK,))
        y += int(h_font.size * 1.35)

    if body_h:
        y += gap_body
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(*TEXT_MUTED_DARK,))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


# ============================================================ Layout G ====
def render_G(slide, index, total, photo_path, brand_handle, accent):
    """ランキング/数字強調: フルブリード写真＋アウトライン数字＋太字見出し"""
    img = full_bleed_bg(photo_path, top_alpha=0.20, bottom_alpha=0.85)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent)

    max_w = WIDTH - MARGIN * 2
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 62, 40, 2)
    heading_h = int(h_font.size * 1.35) * len(h_lines)

    b_font, b_lines, body_h = None, [], 0
    if slide.get("body"):
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_BOLD, max_w, 36, 26, 4)
        body_h = int(b_font.size * 1.6) * len(b_lines)

    num_font = _f(FONT_BLACK, 150)
    num_text = str(index + 1) if slide.get("role") not in ("hook", "summary_cta") else ("Q" if slide.get("role") == "hook" else "✓")
    num_h = 150

    gap1, gap2 = 20, 28
    block_h = num_h + gap1 + heading_h + (gap2 + body_h if body_h else 0)
    y = HEIGHT - FOOTER_H - 56 - block_h

    nbbox = draw.textbbox((0, 0), num_text, font=num_font)
    nh = nbbox[3] - nbbox[1]
    # アウトライン風(縁取り)の数字: 少しずつずらして accent を重ね描きしてから本体を白抜きに
    ox, oy = MARGIN, y - nbbox[1]
    for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, -3), (0, 3), (-3, 0), (3, 0)]:
        draw.text((ox + dx, oy + dy), num_text, font=num_font, fill=accent)
    draw.text((ox, oy), num_text, font=num_font, fill=NAVY)
    y += num_h + gap1

    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_DARK,))
        y += int(h_font.size * 1.35)

    if body_h:
        y += gap2
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(*TEXT_MUTED_DARK,))
            y += int(b_font.size * 1.6)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


# ============================================================ Layout I ====
def render_I(slide, index, total, photo_path, brand_handle, accent):
    """写真全面＋短文: エディトリアル/雑誌風。マーカーハイライト見出しのみ"""
    img = full_bleed_bg(photo_path, top_alpha=0.18, bottom_alpha=0.78)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent)

    max_w = WIDTH - MARGIN * 2 - 40
    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 78, 46, 3)
    line_h = int(h_font.size * 1.4)
    total_h = line_h * len(h_lines)
    y = HEIGHT - FOOTER_H - 70 - total_h
    _highlight_lines(draw, h_lines, h_font, WIDTH / 2, y, line_h, accent)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


# ============================================================ Layout J ====
def render_J(slide, index, total, photo_path, brand_handle, accent):
    """カード型: 大きめ角丸写真カード(画面の大部分)＋バッジ＋太字見出し"""
    img = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    draw = ImageDraw.Draw(img)
    _brand_mark(draw, accent, on_dark=False)

    photo = _load_photo(photo_path)
    card_top, card_h = 90, 760
    if photo:
        p = cover_resize_crop(photo, WIDTH - MARGIN * 2, card_h)
        p = darken_photo(p, 0.05, 0.55)
        mask = Image.new("L", p.size, 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle((0, 0, p.size[0], p.size[1]), radius=32, fill=255)
        card_img = Image.new("RGB", p.size, OFFWHITE)
        card_img.paste(p, (0, 0), mask)
        img.paste(card_img, (MARGIN, card_top), mask)

    max_w = WIDTH - MARGIN * 2
    y = card_top + card_h + 40
    if slide.get("role") in ROLE_LABELS and slide.get("role") != "hook":
        _pill_badge(draw, ROLE_LABELS[slide["role"]], MARGIN, y, accent)
        y += 74

    h_font, h_lines = fit_wrapped_text(draw, slide["heading"], FONT_BLACK, max_w, 56, 36, 2)
    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=(*TEXT_ON_LIGHT,))
        y += int(h_font.size * 1.32)

    if slide.get("body"):
        y += 8
        b_font, b_lines = fit_wrapped_text(draw, slide["body"], FONT_BOLD, max_w, 34, 26, 2)
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(60, 58, 52))
            y += int(b_font.size * 1.5)

    _footer_bar(img, index, total, brand_handle, accent)
    return img


LAYOUT_RENDERERS = {
    "A": render_A,
    "C": render_C,
    "E": render_E,
    "G": render_G,
    "I": render_I,
    "J": render_J,
}


def render_slide(layout_type: str, slide: dict, index: int, total: int, photo_path: str | None, brand_handle: str, accent_seed: int = 0) -> Image.Image:
    renderer = LAYOUT_RENDERERS.get(layout_type)
    if renderer is None:
        raise ValueError(f"未実装のレイアウトです: {layout_type}")
    accent = pick_accent(accent_seed)
    return renderer(slide, index, total, photo_path, brand_handle, accent)
