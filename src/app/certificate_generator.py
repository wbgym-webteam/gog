#gog\src\app\certificate_generator.py
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CERT_TEMPLATE = Path(__file__).parent / 'static' / 'certificates' / 'Urkunde_ohne_Datum.PNG'
# Fonts are bundled under static/fonts/ so the app works on any OS
FONT_DIR = Path(__file__).parent / 'static' / 'fonts'


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / filename
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                   x_left: int, x_right: int, y_top: int, y_bottom: int,
                   fill: tuple = (0, 0, 0)):
    """Draw text centered inside a bounding box, correctly accounting for font metrics."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cx = (x_left + x_right) // 2
    cy = (y_top + y_bottom) // 2
    # Subtract bbox[0/1] to compensate for the font's internal origin offset
    x = cx - text_w // 2 - bbox[0]
    y = cy - text_h // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def generate_certificate(team_name: str, year: int, place: int) -> bytes:
    """
    Overlay team_name, year and place onto the certificate template.
    Returns PNG bytes.

    Image dimensions: 2480 x 3508 (A4 @ 300 dpi)

    Measured pixel regions:
      "DAS TEAM" text band       : y=908-973,  x=652-1088  (left part)
      Team-name blank underline  : y=986-997,  x=1117-1834
      "HAT BEIM..." text band    : y=1023-1088
      Year blank underline       : y=1101-1112, x=1609-1895
      "1. PLATZ" text band       : y=1524-1694, x=798-1709
    """
    img = Image.open(CERT_TEMPLATE).convert('RGBA')
    background = Image.new('RGBA', img.size, (255, 255, 255, 255))
    background.paste(img, mask=img)
    img = background.convert('RGB')
    draw = ImageDraw.Draw(img)

    # Century Gothic Bold — matches the certificate's existing body font
    # Size 87 gives ~65 px cap-height, matching the "DAS TEAM" text band height
    font_body = _load_font('GOTHICB.TTF', 87)
    font_platz = _load_font('GOTHICB.TTF', 240)

    # ── Team name ────────────────────────────────────────────────────────────
    # Erase only the underline (y=983-1000), keep the text band clean
    draw.rectangle([1100, 983, 1850, 1002], fill='white')
    # Also clear any leftover artefacts above
    draw.rectangle([1100, 906, 1850, 982], fill='white')

    name_upper = team_name.upper()
    # Auto-shrink if the name is too wide for the blank space
    f = font_body
    max_w = 1834 - 1117 - 20
    while True:
        bb = draw.textbbox((0, 0), name_upper, font=f)
        if (bb[2] - bb[0]) <= max_w or f.size <= 40:
            break
        f = _load_font('GOTHICB.TTF', f.size - 5)

    # Center within the exact text band (same vertical span as "DAS TEAM")
    _draw_centered(draw, name_upper, f, 1117, 1834, 908, 973)

    # ── Year ─────────────────────────────────────────────────────────────────
    draw.rectangle([1600, 1098, 1905, 1116], fill='white')
    draw.rectangle([1600, 1021, 1905, 1097], fill='white')

    # Center within the exact text band (same vertical span as "HAT BEIM...")
    _draw_centered(draw, str(year), font_body, 1609, 1895, 1023, 1088)

    # ── Placement text ───────────────────────────────────────────────────────
    draw.rectangle([680, 1515, 1820, 1710], fill='white')
    _draw_centered(draw, f'{place}. PLATZ', font_platz, 680, 1820, 1524, 1694)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
