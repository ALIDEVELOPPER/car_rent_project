"""Support multilingue (français / arabe) pour les PDF (facture, contrat).

L'arabe demande un traitement particulier avec reportlab :
- une police qui contient les glyphes arabes (Amiri, embarquée) ;
- `arabic_reshaper` pour choisir la forme contextuelle des lettres ;
- `python-bidi` pour ré-ordonner en ordre d'affichage (droite→gauche).

reportlab ne fait rien de tout ça nativement. On pré-forme donc chaque *ligne*
avant de la passer à un Paragraph aligné à droite.
"""
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.paths import get_assets_dir

_FONTS_DIR = get_assets_dir() / "fonts"
_fonts_ok = False
_tried = False


def ensure_fonts() -> bool:
    global _fonts_ok, _tried
    if _tried:
        return _fonts_ok
    _tried = True
    try:
        pdfmetrics.registerFont(TTFont("Amiri", str(_FONTS_DIR / "Amiri-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Amiri-Bold", str(_FONTS_DIR / "Amiri-Bold.ttf")))
        _fonts_ok = True
    except Exception:  # noqa: BLE001 - pas de police arabe => on retombe sur le français
        _fonts_ok = False
    return _fonts_ok


def _shape_line(text: str) -> str:
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(str(text)))


class PdfLang:
    """Encapsule tout ce qui dépend de la langue pour un document PDF."""

    def __init__(self, lang: str | None):
        self.lang = "ar" if lang == "ar" else "fr"
        self.rtl = self.lang == "ar" and ensure_fonts()
        self.font = "Amiri" if self.rtl else "Helvetica"
        self.font_bold = "Amiri-Bold" if self.rtl else "Helvetica-Bold"
        self.align = TA_RIGHT if self.rtl else TA_LEFT

    def tr(self, text) -> str:
        """Chaîne courte tenant sur une seule ligne."""
        if text in (None, ""):
            return ""
        return _shape_line(text) if self.rtl else str(text)

    def wrap(self, text, max_chars: int = 95) -> str:
        """Chaîne longue : découpe en lignes, chacune formée séparément, jointes
        par <br/> (Paragraph). En français, renvoie le texte tel quel."""
        if not self.rtl:
            return str(text)
        words = str(text).split()
        lines: list[str] = []
        current = ""
        for word in words:
            if current and len(current) + 1 + len(word) > max_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
        return "<br/>".join(_shape_line(line) for line in lines)

    def kv(self, label: str, value) -> list:
        """Ligne clé/valeur d'un tableau, dans le bon ordre visuel."""
        return [self.tr(value), self.tr(label)] if self.rtl else [self.tr(label), self.tr(value)]
