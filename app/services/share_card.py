"""Рендер шер-карточек (PNG) для соцсетей — вирусность.

Карточка прогресса: бренд ID BJJ + пояс + ранг/уровень + XP + @хендл бота.
Делается через Pillow без эмодзи (только текст/фигуры — цветной эмодзи Pillow не
рисует). Шрифты — DejaVu (кириллица), в проде ставятся в Docker (fonts-dejavu-core);
локально ищем системные фолбэки. Размер 1080×1350 (4:5 — сторис/лента).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services import i18n
from app.services import progress as progress_svc

log = logging.getLogger(__name__)

W, H = 1080, 1350
BG = (255, 255, 255)
INK = (10, 10, 10)
MUT = (107, 114, 128)
LINE = (231, 231, 231)
SOFT = (240, 240, 240)

# Канонический пояс → цвет полосы на карточке.
BELT_HEX = {
    "white": (232, 232, 232),
    "blue": (37, 99, 235),
    "purple": (124, 58, 237),
    "brown": (124, 74, 30),
    "black": (17, 24, 39),
}

_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",          # Linux (prod)
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",            # macOS
    "/Library/Fonts/Arial Bold.ttf",
]
_REG_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (_BOLD_CANDIDATES if bold else _REG_CANDIDATES):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    l, _t, r, _b = draw.textbbox((0, 0), text, font=font)
    return r - l


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill) -> None:
    draw.text(((W - _w(draw, text, font)) // 2, y), text, font=font, fill=fill)


def render_progress_card(
    *, belt: str | None, stripes: int, xp: int, name: str | None, lang: str | None
) -> bytes:
    """PNG-байты карточки прогресса ученика."""
    info = progress_svc.level_info(xp or 0)
    level = info["level"]
    title = i18n.level_title(level, lang)
    belt_label = i18n.belt_label(belt, lang) if belt else "—"
    belt_color = BELT_HEX.get(belt or "", (156, 163, 175))

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 30], outline=LINE, width=4)

    # Лого: «ID» в рамке + «BJJ».
    f_logo = _font(64, bold=True)
    pad, gap = 16, 16
    id_t, bjj_t = "ID", "BJJ"
    iw, bw = _w(d, id_t, f_logo), _w(d, bjj_t, f_logo)
    total = iw + 2 * pad + gap + bw
    x0, y0 = (W - total) // 2, 96
    d.rectangle([x0 - pad, y0 - 8, x0 + iw + pad, y0 + 78], outline=INK, width=5)
    d.text((x0, y0), id_t, font=f_logo, fill=INK)
    d.text((x0 + iw + 2 * pad + gap, y0), bjj_t, font=f_logo, fill=INK)

    if name:
        _center(d, 220, name[:24], _font(40, bold=True), INK)

    # Пояс — цветная полоса с чёрным «бар» и белыми полосками (как на ги-поясе).
    by, bh = 380, 150
    bx0, bx1 = 110, W - 110
    d.rounded_rectangle([bx0, by, bx1, by + bh], radius=18, fill=belt_color, outline=INK, width=5)
    barw = 170
    d.rectangle([bx1 - barw - 28, by + 12, bx1 - 28, by + bh - 12], fill=INK)
    for i in range(max(0, min(stripes or 0, 4))):
        sx = bx1 - barw - 28 + 22 + i * 34
        d.rectangle([sx, by + 28, sx + 14, by + bh - 28], fill=(255, 255, 255))

    _center(d, by + bh + 44, belt_label.upper(), _font(58, bold=True), INK)
    _center(d, by + bh + 138, title, _font(48, bold=True), INK)
    _center(d, by + bh + 210, f"{i18n.t(lang, 'card_level')} {level}", _font(38), MUT)

    # XP-бар.
    px0, px1 = 160, W - 160
    py, ph = by + bh + 300, 36
    d.rounded_rectangle([px0, py, px1, py + ph], radius=ph // 2, fill=SOFT)
    frac = info["into"] / info["per_level"] if info["per_level"] else 0
    fillw = int((px1 - px0) * frac)
    if fillw >= ph:
        d.rounded_rectangle([px0, py, px0 + fillw, py + ph], radius=ph // 2, fill=INK)
    _center(d, py + ph + 18, f"{info['into']}/{info['per_level']} XP", _font(30), MUT)

    # Футер — хендл и сайт едут вместе с картинкой при репосте.
    _center(d, H - 150, "@ID_BJJ_onlinebot", _font(40, bold=True), INK)
    _center(d, H - 92, "idbjjapp.ru", _font(32), MUT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
