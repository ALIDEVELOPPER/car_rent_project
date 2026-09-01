"""Génère l'icône de l'app Krilia (frontend/assets/logo/icon.png + icon.ico) :
monogramme "K" blanc sur un carré arrondi à dégradé indigo → violet, cohérent
avec .logo-mark des écrans de connexion. Usage ponctuel, pas exécuté au build.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TOP = (99, 102, 241)      # indigo-500
BOTTOM = (124, 58, 237)   # violet-600
CONTRAST = "#ffffff"
SIZE = 512
OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "logo"


def _find_bold_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient(size: int) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        f = y / (size - 1)
        grad.putpixel(
            (0, y),
            tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * f) for i in range(3)),
        )
    return grad.resize((size, size))


def build_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    radius = int(SIZE * 0.24)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=radius, fill=255)
    img.paste(_gradient(SIZE), (0, 0), mask)

    draw = ImageDraw.Draw(img)
    font = _find_bold_font(int(SIZE * 0.5))
    text = "K"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((SIZE - text_w) / 2 - bbox[0], (SIZE - text_h) / 2 - bbox[1])
    draw.text(pos, text, font=font, fill=CONTRAST)

    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    icon = build_icon()

    png_path = OUT_DIR / "icon.png"
    icon.save(png_path)

    ico_path = OUT_DIR / "icon.ico"
    icon.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    print(f"Écrit : {png_path}")
    print(f"Écrit : {ico_path}")


if __name__ == "__main__":
    main()
