"""日本語テキストのフィット/折り返しユーティリティ(スペース無し言語向け、孤立行回避つき)"""
from PIL import ImageFont


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap_text(draw, text, f, max_width):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=f)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def fit_wrapped_text(draw, text, font_path, max_width, max_size, min_size, max_lines, step=2):
    """できるだけ大きいフォントサイズで、孤立した短い最終行を避けつつ折り返す"""
    best = None
    for size in range(max_size, min_size - 1, -step):
        f = font(font_path, size)
        lines = wrap_text(draw, text, f, max_width)
        if len(lines) > max_lines:
            continue
        if best is None:
            best = (f, lines)
        if len(lines) >= 2 and len(lines[-1]) < 3 and len(lines[-1]) < len(lines[-2]):
            continue
        return f, lines
    if best is not None:
        return best
    f = font(font_path, min_size)
    return f, wrap_text(draw, text, f, max_width)


def draw_multiline(draw, lines, f, x, y, line_height, fill, center_x=None):
    for line in lines:
        if center_x is not None:
            bbox = draw.textbbox((0, 0), line, font=f)
            w = bbox[2] - bbox[0]
            draw.text((center_x - w / 2, y), line, font=f, fill=fill)
        else:
            draw.text((x, y), line, font=f, fill=fill)
        y += line_height
    return y


def blend(c1, c2, t):
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
