"""PDF d'un état des lieux (départ ou retour), français / arabe."""
import io
from pathlib import Path

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.agence import get_or_create_agence
from app.services.pdf_i18n import PdfLang

STR = {
    "fr": {
        "titre": {"depart": "ÉTAT DES LIEUX — DÉPART", "retour": "ÉTAT DES LIEUX — RETOUR"},
        "contrat": "Contrat n°", "date": "Effectué le",
        "locataire": "Locataire", "vehicule": "Véhicule", "immat": "Immatriculation",
        "km": "Kilométrage", "carburant": "Niveau de carburant",
        "degats": "Dégâts constatés", "observations": "Observations",
        "aucun_degat": "Aucun dégât constaté.",
        "photos": "Photos", "sign_client": "Signature du locataire", "sign_agence": "Pour l'agence",
        "carb": {"vide": "Vide", "quart": "1/4", "moitie": "1/2", "trois_quarts": "3/4", "plein": "Plein"},
    },
    "ar": {
        "titre": {"depart": "محضر معاينة — عند الانطلاق", "retour": "محضر معاينة — عند الإرجاع"},
        "contrat": "عقد رقم", "date": "أُنجز في",
        "locataire": "المكتري", "vehicule": "السيارة", "immat": "رقم التسجيل",
        "km": "عدد الكيلومترات", "carburant": "مستوى الوقود",
        "degats": "الأضرار المعاينة", "observations": "ملاحظات",
        "aucun_degat": "لم تُعاين أي أضرار.",
        "photos": "الصور", "sign_client": "توقيع المكتري", "sign_agence": "عن الوكالة",
        "carb": {"vide": "فارغ", "quart": "الربع", "moitie": "النصف", "trois_quarts": "ثلاثة أرباع", "plein": "ممتلئ"},
    },
}


def _fmt_dt(value) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else "……………………"


def render_etat_des_lieux_pdf(etat) -> bytes:
    reservation = etat.reservation
    client = reservation.client
    vehicule = reservation.vehicule
    agence = get_or_create_agence()
    pl = PdfLang(agence.langue)
    s = STR[pl.lang]

    normal = ParagraphStyle("n", fontName=pl.font, fontSize=9.5, leading=13, alignment=pl.align)
    section = ParagraphStyle("s", fontName=pl.font_bold, fontSize=10, spaceBefore=10, spaceAfter=4, alignment=pl.align)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, title="État des lieux")
    e = []

    e.append(Paragraph(f"<b>{pl.tr(agence.nom)}</b>", ParagraphStyle("h", parent=normal, fontSize=13)))
    if agence.adresse:
        e.append(Paragraph(pl.tr(agence.adresse), normal))
    e.append(Spacer(1, 0.3 * cm))

    e.append(Paragraph(f"<b>{pl.tr(s['titre'][etat.type.value])}</b>",
                       ParagraphStyle("t", fontName=pl.font_bold, fontSize=14, leading=18,
                                      alignment=1, spaceAfter=5)))
    e.append(Paragraph(pl.tr(f"{s['contrat']} {reservation.id:05d}    —    {s['date']} {_fmt_dt(etat.date_effectue)}"),
                       ParagraphStyle("sub", parent=normal, alignment=1, leading=12,
                                      spaceBefore=2, textColor=colors.HexColor("#555555"))))
    e.append(Spacer(1, 0.2 * cm))
    e.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")))

    carb = s["carb"].get(etat.niveau_carburant.value) if etat.niveau_carburant else "……………………"
    rows = [
        pl.kv(s["locataire"], f"{client.prenom} {client.nom}"),
        pl.kv(s["vehicule"], f"{vehicule.marque} {vehicule.modele}"),
        pl.kv(s["immat"], vehicule.immatriculation),
        pl.kv(s["km"], str(etat.kilometrage) if etat.kilometrage is not None else "……………………"),
        pl.kv(s["carburant"], carb),
    ]
    t = Table(rows, colWidths=[doc.width * 0.72, doc.width * 0.28] if pl.rtl else [doc.width * 0.28, doc.width * 0.72])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), pl.font), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
        ("TEXTCOLOR", (1 if pl.rtl else 0, 0), (1 if pl.rtl else 0, -1), colors.HexColor("#555555")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    e.append(t)

    e.append(Paragraph(pl.tr(s["degats"]), section))
    e.append(Paragraph(pl.wrap(etat.degats) if etat.degats else pl.tr(s["aucun_degat"]), normal))

    if etat.observations:
        e.append(Paragraph(pl.tr(s["observations"]), section))
        e.append(Paragraph(pl.wrap(etat.observations), normal))

    # Photos
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    images = []
    for rel in etat.photos_liste:
        p = (upload_root / rel).resolve()
        try:
            if p.is_relative_to(upload_root.resolve()) and p.exists():
                images.append(Image(str(p), width=doc.width / 2 - 6, height=(doc.width / 2 - 6) * 0.7, kind="proportional"))
        except (OSError, ValueError):
            continue
    if images:
        e.append(Paragraph(pl.tr(s["photos"]), section))
        for i in range(0, len(images), 2):
            e.append(Table([images[i:i + 2]], colWidths=[doc.width / 2] * min(2, len(images) - i)))
            e.append(Spacer(1, 0.2 * cm))

    # Signatures
    sign_row = [s["sign_client"], s["sign_agence"]]
    if pl.rtl:
        sign_row = [pl.tr(x) for x in reversed(sign_row)]
    sign = Table([sign_row, ["", ""]], colWidths=[doc.width / 2] * 2, rowHeights=[0.5 * cm, 1.8 * cm])
    sign.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), pl.font), ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
        ("LINEBELOW", (0, 1), (0, 1), 0.5, colors.HexColor("#333333")),
        ("LINEBELOW", (1, 1), (1, 1), 0.5, colors.HexColor("#333333")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    e.append(KeepTogether([Spacer(1, 0.6 * cm), sign]))

    doc.build(e)
    return buffer.getvalue()
