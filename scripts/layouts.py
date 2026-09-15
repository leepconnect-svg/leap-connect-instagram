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

from PIL import Image, ImageChops, ImageDraw, ImageFilter

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
    "problem": "問題提起",
    "cause": "原因",
    "risk": "リスク",
    "solution": "対策",
    "method_1": "活用アイデア",
    "method_2": "活用アイデア",
    "method_3": "活用アイデア",
    "summary_cta": "まとめ",
}

# 「空室の時間貸し/多用途活用」専用構成(generate_script.pyのVACANCY_REUSE_PROMPT_TEMPLATE)
# のmethod_1〜3スライドに表示する大きな番号
METHOD_NUMBER_MAP = {"method_1": "01", "method_2": "02", "method_3": "03"}


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
def render_A(slide, index, total, photo_path, brand_handle, accent, **_meta):
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
def render_C(slide, index, total, photo_path, brand_handle, accent, **_meta):
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
def render_E(slide, index, total, photo_path, brand_handle, accent, **_meta):
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
def render_G(slide, index, total, photo_path, brand_handle, accent, **_meta):
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
def render_I(slide, index, total, photo_path, brand_handle, accent, **_meta):
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
def render_J(slide, index, total, photo_path, brand_handle, accent, **_meta):
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


# ============================================================ Layout K ====
NAVY_BADGE = (14, 24, 58)
BLUE_ACCENT = (28, 58, 128)
YELLOW = (255, 199, 40)
BLACK_TEXT = (20, 20, 22)

LIST_STRUCTURE_TYPES = {"ランキング型", "チェックリスト型", "数字型", "比較型"}


def _left_light_panel(img: Image.Image, strength=0.94, edge=0.60, fade_width=0.18) -> Image.Image:
    """写真の左側を白っぽくフェードさせ、太字テキストを乗せても読みやすくする
    (実際の人気投稿にあった「カーテンの白い壁に文字が乗っている」効果を再現)"""
    w, h = img.size
    row = []
    for x in range(w):
        t = x / w
        if t < edge:
            a = strength
        else:
            fade = min(1.0, (t - edge) / fade_width)
            a = strength * (1 - fade)
        row.append(int(255 * max(0.0, a)))
    overlay = Image.new("L", (w, h))
    overlay.putdata(row * h)
    white_layer = Image.new("RGB", (w, h), WHITE)
    return Image.composite(white_layer, img.convert("RGB"), overlay)


def _light_panel_zone(img: Image.Image, y_top: int, y_bottom: int, strength=0.94, edge=0.60, fade_width=0.18, v_fade=110) -> Image.Image:
    """写真の左側を白っぽくフェードさせるが、縦方向は[y_top, y_bottom]付近のみに限定する。
    テキスト量が少ないスライドでも、余った部分を「白い空白」にせず実際の写真をそのまま見せるための処理
    (以前は全高にパネルをかけていたため、文章が短いスライドで下部が間延びした白い余白に見えていた)"""
    w, h = img.size

    # 横方向のアルファ(_left_light_panelと同じロジック)
    row = []
    for x in range(w):
        t = x / w
        if t < edge:
            a = strength
        else:
            fade = min(1.0, (t - edge) / fade_width)
            a = strength * (1 - fade)
        row.append(int(255 * max(0.0, a)))
    overlay_h = Image.new("L", (w, h))
    overlay_h.putdata(row * h)

    # 縦方向のアルファ: y_top〜y_bottomの範囲は1.0、その外側はv_fade pxかけて0(写真そのまま)へフェード
    col = []
    for y in range(h):
        if y_top <= y <= y_bottom:
            a = 1.0
        elif y < y_top:
            a = max(0.0, 1.0 - (y_top - y) / v_fade)
        else:
            a = max(0.0, 1.0 - (y - y_bottom) / v_fade)
        col.append(int(255 * a))
    overlay_v_col = Image.new("L", (1, h))
    overlay_v_col.putdata(col)
    overlay_v = overlay_v_col.resize((w, h), Image.NEAREST)

    overlay = ImageChops.multiply(overlay_h, overlay_v)
    white_layer = Image.new("RGB", (w, h), WHITE)
    return Image.composite(white_layer, img.convert("RGB"), overlay)


def _speech_bubble(draw, text, x, y, font_size=32):
    tag_font = _f(FONT_BLACK, font_size)
    bbox = draw.textbbox((0, 0), text, font=tag_font)
    w = bbox[2] - bbox[0]
    pad_x, pad_y = 26, 16
    box = (x, y, x + w + pad_x * 2, y + font_size + pad_y * 2)
    draw.rounded_rectangle(box, radius=14, fill=NAVY_BADGE)
    draw.text((x + pad_x, y + pad_y - 4), text, font=tag_font, fill=WHITE)

    # 右上に黄色いスパークル(注目線)を3本添える
    sx, sy = box[2] + 14, box[1] - 4
    for i, (dx, dy, length) in enumerate([(0, 10, 26), (12, -4, 22), (16, 16, 24)]):
        draw.line((sx + dx, sy + dy, sx + dx + length * 0.5, sy + dy - length), fill=YELLOW, width=6)
    return box[3] - box[1]


def _draw_heading_with_emphasis(draw, heading, emphasis, font_obj, x, y, line_height, max_width):
    """headingを1文字ずつ描画し、emphasis部分だけ色を変える(強調語がなければ全て黒字)"""
    lines = wrap_text(draw, heading, font_obj, max_width)
    emp_start = heading.find(emphasis) if emphasis else -1
    emp_end = emp_start + len(emphasis) if emp_start >= 0 else -1

    idx = 0
    cy = y
    for line in lines:
        cx = x
        for ch in line:
            color = BLUE_ACCENT if emp_start <= idx < emp_end else BLACK_TEXT
            draw.text((cx, cy), ch, font=font_obj, fill=color)
            bbox = draw.textbbox((0, 0), ch, font=font_obj)
            cx += bbox[2] - bbox[0]
            idx += 1
        cy += line_height
    return lines, cy


def _bullet_badge(draw, text, x, y, max_width):
    """チェックアイコン付きの紺色バッジ(実際の人気投稿にあった「知らないと損！」的な一言用)"""
    badge_font = _f(FONT_BOLD, 30)
    bbox = draw.textbbox((0, 0), text, font=badge_font)
    text_w = min(bbox[2] - bbox[0], max_width - 90)
    pad_x, pad_y, icon_gap = 22, 14, 46
    box_h = 30 + pad_y * 2
    box = (x, y, x + icon_gap + text_w + pad_x * 2, y + box_h)
    draw.rounded_rectangle(box, radius=box_h // 2, fill=NAVY_BADGE)
    # チェックアイコン(黄色い丸+黒いチェック)
    icon_cx, icon_cy = x + pad_x + 14, y + box_h / 2
    draw.ellipse((icon_cx - 14, icon_cy - 14, icon_cx + 14, icon_cy + 14), fill=YELLOW)
    draw.line((icon_cx - 6, icon_cy, icon_cx - 1, icon_cy + 6), fill=NAVY_BADGE, width=4)
    draw.line((icon_cx - 1, icon_cy + 6, icon_cx + 8, icon_cy - 7), fill=NAVY_BADGE, width=4)
    draw.text((x + pad_x + icon_gap, y + pad_y - 2), text, font=badge_font, fill=WHITE)
    return box[3] - box[1]


def render_K(slide, index, total, photo_path, brand_handle, accent, structure_type=None, total_items=None, **_meta):
    """吹き出しタグ＋黒字/ネイビー強調見出し＋チェックバッジ。
    実際にleap_connectで反応が良かった過去投稿(人が作成)のデザインを再現したメインレイアウト。"""
    photo = _load_photo(photo_path)
    has_photo = photo is not None
    if has_photo:
        base = cover_resize_crop(photo, WIDTH, HEIGHT)
    else:
        base = Image.new("RGB", (WIDTH, HEIGHT), OFFWHITE)
    # 測定専用のDraw(textbbox/textlength/wrap_textはピクセルを描画しないので、
    # 白パネルを重ねる前のbaseに対して安全に呼び出せる)
    meas_draw = ImageDraw.Draw(base)

    text_max_w = int(WIDTH * 0.66) - MARGIN

    # 吹き出しタグ(常に上部の同じ位置に固定。デザインの一貫性のため)
    if index == 0:
        tag_text = f"{slide.get('_category', 'オーナー')}オーナー必見！"
    else:
        tag_text = ROLE_LABELS.get(slide.get("role"), "POINT")
    tag_font_size = 32
    tag_h = tag_font_size + 32  # _speech_bubbleの内部計算(pad_y=16)と一致させた固定値
    tag_y = 64
    content_top = tag_y + tag_h + 34

    # 下部のチェックバッジ(0〜3個)の占有領域を先に計算しておく
    # (本文の描画量に関わらず、バッジと重ならないようにするため)
    bullets = slide.get("bullets") or []
    gap, est_h = 18, 62
    bullets_zone_h = (est_h * len(bullets) + gap * (len(bullets) - 1)) if bullets else 0
    bullets_top = HEIGHT - FOOTER_H - 40 - bullets_zone_h
    content_bottom = bullets_top - 24
    available_h = max(80, content_bottom - content_top)

    # 見出しフォント(5行以内に収まる最大サイズを採用)
    max_size, min_size = (58, 38) if index == 0 else (50, 34)
    h_font = None
    for size in range(max_size, min_size - 1, -2):
        candidate = _f(FONT_BLACK, size)
        lines = wrap_text(meas_draw, slide["heading"], candidate, text_max_w)
        if len(lines) <= 5:
            h_font = candidate
            break
    if h_font is None:
        h_font = _f(FONT_BLACK, min_size)
    h_line_h = int(h_font.size * 1.28)
    heading_lines = wrap_text(meas_draw, slide["heading"], h_font, text_max_w)
    heading_block_h = h_line_h * len(heading_lines)

    # method_1〜3スライドは、見出しの直前に大きな番号(01/02/03)を表示する
    method_num = METHOD_NUMBER_MAP.get(slide.get("role"))
    GAP_NUM = 16
    num_font = _f(FONT_BLACK, 110) if method_num else None
    num_block_h = (meas_draw.textbbox((0, 0), method_num, font=num_font)[3] + GAP_NUM) if method_num else 0

    # 1枚目かつリスト系の構成タイプなら、見出しの直後に「4選」のような大きな数字を添える
    show_lead_number = bool(index == 0 and total_items and structure_type in LIST_STRUCTURE_TYPES)
    GAP_LEAD = 12
    lead_block_h = (GAP_LEAD + 150) if show_lead_number else 0

    # 本文: 使える余白をできるだけ活かす大きめのフォントを選ぶ(小さい文字で下に空白を残さない)
    body_text = slide.get("body") or ""
    GAP_BODY = 22
    fixed_h = num_block_h + heading_block_h + lead_block_h + (GAP_BODY if body_text else 0)
    body_budget = max(0, available_h - fixed_h)

    b_font = b_lines = None
    b_line_h = 0
    body_block_h = 0
    if body_text:
        for size in range(36, 21, -2):
            candidate = _f(FONT_BOLD, size)
            lines = wrap_text(meas_draw, body_text, candidate, text_max_w)
            line_h = int(size * 1.6)
            block_h = line_h * len(lines)
            if len(lines) <= 5 and block_h <= body_budget:
                b_font, b_lines, b_line_h, body_block_h = candidate, lines, line_h, block_h
                break
        if b_font is None:
            # どのサイズでも収まらない場合は最小サイズを採用し、行を切り詰める
            size = 22
            b_font = _f(FONT_BOLD, size)
            b_line_h = int(size * 1.6)
            lines = wrap_text(meas_draw, body_text, b_font, text_max_w)
            max_fit_lines = max(1, int(body_budget // b_line_h)) if body_budget > 0 else 1
            b_lines = lines[:max_fit_lines]
            if len(lines) > max_fit_lines and b_lines:
                b_lines[-1] = (b_lines[-1][:-1] + "…") if len(b_lines[-1]) > 1 else "…"
            body_block_h = b_line_h * len(b_lines)

    total_block_h = fixed_h + body_block_h
    block_bottom = content_top + total_block_h

    # --- 写真を活かすため、白パネルは「タグ＋テキストがある範囲」だけに絞る ---
    # (文章量が少ないスライドでも、余った部分は空白にせず実際の写真をそのまま見せる。
    #  以前は写真全高に白パネルをかけていたため、短い文章のスライドで
    #  上下に間延びした白い空白が目立っていた)
    if has_photo:
        panel_top = max(0, tag_y - 24)
        panel_bottom = min(HEIGHT, block_bottom + 40)
        img = _light_panel_zone(base, panel_top, panel_bottom)
    else:
        img = base
    draw = ImageDraw.Draw(img)

    # --- ここから実際の描画(測定済みのフォント/行/高さをそのまま使い、二重測定しない) ---
    _speech_bubble(draw, tag_text, MARGIN, tag_y, font_size=tag_font_size)

    y = content_top
    if method_num:
        draw.text((MARGIN, y), method_num, font=num_font, fill=BLUE_ACCENT)
        y += num_block_h

    _, y = _draw_heading_with_emphasis(draw, slide["heading"], slide.get("emphasis", ""), h_font, MARGIN, y, h_line_h, text_max_w)

    if show_lead_number:
        y += GAP_LEAD
        lead_num_font = _f(FONT_BLACK, 130)
        suffix_font = _f(FONT_BLACK, 60)
        num_text = str(total_items)
        draw.text((MARGIN, y), num_text, font=lead_num_font, fill=BLUE_ACCENT)
        nbbox = draw.textbbox((MARGIN, y), num_text, font=lead_num_font)
        draw.text((nbbox[2] + 6, y + 60), "選", font=suffix_font, fill=BLACK_TEXT)
        y += 150

    if body_text:
        y += GAP_BODY
        for line in b_lines:
            draw.text((MARGIN, y), line, font=b_font, fill=(70, 68, 64))
            y += b_line_h

    if bullets:
        by = bullets_top
        for b in bullets:
            h = _bullet_badge(draw, b, MARGIN, by, WIDTH - MARGIN * 2)
            by += h + gap

    _footer_bar(img, index, total, brand_handle, accent)
    return img


LAYOUT_RENDERERS = {
    "A": render_A,
    "C": render_C,
    "E": render_E,
    "G": render_G,
    "I": render_I,
    "J": render_J,
    "K": render_K,
}


def render_slide(
    layout_type: str,
    slide: dict,
    index: int,
    total: int,
    photo_path: str | None,
    brand_handle: str,
    accent_seed: int = 0,
    structure_type: str | None = None,
    total_items: int | None = None,
    category: str | None = None,
) -> Image.Image:
    renderer = LAYOUT_RENDERERS.get(layout_type)
    if renderer is None:
        raise ValueError(f"未実装のレイアウトです: {layout_type}")
    accent = pick_accent(accent_seed)
    if category:
        slide = {**slide, "_category": category}
    return renderer(slide, index, total, photo_path, brand_handle, accent, structure_type=structure_type, total_items=total_items)
