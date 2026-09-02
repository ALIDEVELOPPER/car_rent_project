import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.extensions import db
from app.models import Facture, Reservation
from app.models.enums import ModePaiement, StatutPaiement
from app.services.agence import get_or_create_agence
from app.services.pdf_i18n import PdfLang

FACTURE_STR = {
    "fr": {
        "facture": "Facture",
        "date_emission": "Date d'émission",
        "client": "Client",
        "col_vehicule": "Véhicule",
        "col_periode": "Période",
        "col_jours": "Jours",
        "col_prix_jour": "Prix / jour",
        "col_montant": "Montant",
        "statut": "Statut",
        "mode_paiement": "Mode de paiement",
        "total_ht": "Total HT",
        "tva": "TVA",
        "total_ttc": "Total TTC",
        "total": "Total",
        "ice": "ICE", "rc": "RC", "if": "IF", "patente": "Patente",
        "statut_labels": {
            "en_attente": "En attente de paiement",
            "payee": "Payée",
            "annulee": "Annulée",
        },
        "mode_labels": {
            "especes": "Espèces", "carte": "Carte", "virement": "Virement", "cheque": "Chèque",
        },
    },
    "ar": {
        "facture": "فاتورة",
        "date_emission": "تاريخ الإصدار",
        "client": "العميل",
        "col_vehicule": "السيارة",
        "col_periode": "المدة",
        "col_jours": "الأيام",
        "col_prix_jour": "الثمن / اليوم",
        "col_montant": "المبلغ",
        "statut": "الحالة",
        "mode_paiement": "طريقة الأداء",
        "total_ht": "المجموع بدون ضريبة",
        "tva": "الضريبة (ض.ق.م)",
        "total_ttc": "المجموع بالضريبة",
        "total": "المجموع",
        "ice": "ICE", "rc": "RC", "if": "IF", "patente": "Patente",
        "statut_labels": {
            "en_attente": "في انتظار الأداء",
            "payee": "مؤداة",
            "annulee": "ملغاة",
        },
        "mode_labels": {
            "especes": "نقدًا", "carte": "بطاقة بنكية", "virement": "تحويل بنكي", "cheque": "شيك",
        },
    },
}

FACTURE_TRANSITIONS: dict[StatutPaiement, set[StatutPaiement]] = {
    StatutPaiement.EN_ATTENTE: {StatutPaiement.PAYEE, StatutPaiement.ANNULEE},
    StatutPaiement.PAYEE: {StatutPaiement.ANNULEE},
    StatutPaiement.ANNULEE: set(),
}


class InvalidPaiementTransitionError(ValueError):
    pass


def _generate_numero_facture(annee: int) -> str:
    prefix = f"FAC-{annee}-"
    count = db.session.execute(
        db.select(db.func.count())
        .select_from(Facture)
        .filter(Facture.numero_facture.like(f"{prefix}%"))
    ).scalar_one()
    return f"{prefix}{count + 1:04d}"


def create_facture_for_reservation(reservation: Reservation) -> Facture:
    existing = db.session.execute(
        db.select(Facture).filter_by(reservation_id=reservation.id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    ttc = Decimal(reservation.montant_total)
    ht = tva = taux = None

    agence = get_or_create_agence()
    if agence.tva_applicable and agence.taux_tva and agence.taux_tva > 0:
        taux = Decimal(agence.taux_tva)
        ht = (ttc / (1 + taux / 100)).quantize(Decimal("0.01"))
        tva = ttc - ht

    facture = Facture(
        reservation_id=reservation.id,
        numero_facture=_generate_numero_facture(now.year),
        date_emission=now,
        montant=ttc,
        montant_ht=ht,
        montant_tva=tva,
        taux_tva=taux,
        statut_paiement=StatutPaiement.EN_ATTENTE,
    )
    db.session.add(facture)
    db.session.flush()
    return facture


def apply_paiement_transition(
    facture: Facture, nouveau_statut: StatutPaiement, mode_paiement: ModePaiement | None = None
) -> None:
    if nouveau_statut not in FACTURE_TRANSITIONS[facture.statut_paiement]:
        raise InvalidPaiementTransitionError(
            f"Transition {facture.statut_paiement.value} -> {nouveau_statut.value} non autorisée"
        )
    if nouveau_statut == StatutPaiement.PAYEE and mode_paiement is None:
        raise ValueError("Le mode de paiement est requis pour marquer une facture payée")

    facture.statut_paiement = nouveau_statut
    if mode_paiement is not None:
        facture.mode_paiement = mode_paiement


def _get_agence_info() -> dict:
    agence = get_or_create_agence()
    return {
        "nom": agence.nom,
        "adresse": agence.adresse or "",
        "telephone": agence.telephone or "",
        "email": agence.email or "",
    }


def _money(value) -> str:
    return str(Decimal(value).quantize(Decimal("0.01")))


def render_facture_pdf(facture: Facture) -> bytes:
    reservation = facture.reservation
    client_obj = reservation.client
    vehicule = reservation.vehicule
    agence_obj = get_or_create_agence()
    agence = _get_agence_info()
    pl = PdfLang(agence_obj.langue)
    s = FACTURE_STR[pl.lang]
    devise = "درهم" if pl.rtl else current_app.config["CURRENCY_LABEL"]

    h1 = ParagraphStyle("h1", fontName=pl.font_bold, fontSize=16, alignment=pl.align, leading=20)
    h2 = ParagraphStyle("h2", fontName=pl.font_bold, fontSize=13, alignment=pl.align, leading=17, spaceBefore=6)
    h3 = ParagraphStyle("h3", fontName=pl.font_bold, fontSize=11, alignment=pl.align, leading=15, spaceBefore=6)
    normal = ParagraphStyle("n", fontName=pl.font, fontSize=9.5, alignment=pl.align, leading=13)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

    elements = [Paragraph(pl.tr(agence["nom"]), h1)]
    if agence["adresse"]:
        elements.append(Paragraph(pl.tr(agence["adresse"]), normal))
    contact_line = " · ".join(filter(None, [agence["telephone"], agence["email"]]))
    if contact_line:
        elements.append(Paragraph(pl.tr(contact_line), normal))
    legal = " · ".join(
        f"{lab} : {val}"
        for lab, val in (
            (s["ice"], agence_obj.ice), (s["rc"], agence_obj.rc),
            (s["if"], agence_obj.identifiant_fiscal), (s["patente"], agence_obj.patente),
        )
        if val
    )
    if legal:
        elements.append(Paragraph(pl.tr(legal), normal))
    elements.append(Spacer(1, 1 * cm))

    elements.append(Paragraph(pl.tr(f"{s['facture']} {facture.numero_facture}"), h2))
    elements.append(
        Paragraph(pl.tr(f"{s['date_emission']} : {facture.date_emission.strftime('%d/%m/%Y')}"), normal)
    )
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph(pl.tr(s["client"]), h3))
    elements.append(Paragraph(pl.tr(f"{client_obj.prenom} {client_obj.nom}"), normal))
    if client_obj.telephone:
        elements.append(Paragraph(pl.tr(client_obj.telephone), normal))
    if client_obj.email:
        elements.append(Paragraph(pl.tr(client_obj.email), normal))
    elements.append(Spacer(1, 0.5 * cm))

    nombre_jours = (reservation.date_fin - reservation.date_debut).days
    header = [
        s["col_vehicule"], s["col_periode"], s["col_jours"],
        f"{s['col_prix_jour']} ({devise})", f"{s['col_montant']} ({devise})",
    ]
    values = [
        f"{vehicule.marque} {vehicule.modele} ({vehicule.immatriculation})",
        f"{reservation.date_debut.strftime('%d/%m/%Y')} - {reservation.date_fin.strftime('%d/%m/%Y')}",
        str(nombre_jours),
        _money(reservation.prix_jour_applique),
        _money(facture.montant),
    ]
    widths = [5 * cm, 4.5 * cm, 1.5 * cm, 3 * cm, 3 * cm]
    if pl.rtl:
        header = [pl.tr(x) for x in reversed(header)]
        values = [pl.tr(x) for x in reversed(values)]
        widths = list(reversed(widths))
    table = Table([header, values], colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), pl.font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))

    # Bloc des totaux, aligné à l'opposé du texte courant.
    if facture.montant_ht is not None:
        totaux = [
            (s["total_ht"], f"{_money(facture.montant_ht)} {devise}"),
            (f"{s['tva']} {facture.taux_tva:g} %", f"{_money(facture.montant_tva)} {devise}"),
            (s["total_ttc"], f"{_money(facture.montant)} {devise}"),
        ]
    else:
        totaux = [(s["total"], f"{_money(facture.montant)} {devise}")]
    rows = []
    for i, (lab, val) in enumerate(totaux):
        bold = i == len(totaux) - 1
        st = ParagraphStyle("tt", parent=normal, fontName=pl.font_bold if bold else pl.font,
                            fontSize=11 if bold else 9.5, alignment=pl.align)
        cells = [Paragraph(pl.tr(val), st), Paragraph(pl.tr(lab), st)]
        rows.append(cells if pl.rtl else list(reversed(cells)))
    tot_widths = [3.5 * cm, 5.5 * cm] if pl.rtl else [5.5 * cm, 3.5 * cm]
    tot_table = Table(rows, colWidths=tot_widths, hAlign="LEFT" if pl.rtl else "RIGHT")
    tot_table.setStyle(TableStyle([
        ("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.7, colors.HexColor("#2c3e50")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
    ]))
    elements.append(tot_table)
    elements.append(Spacer(1, 0.8 * cm))

    elements.append(
        Paragraph(pl.tr(f"{s['statut']} : {s['statut_labels'][facture.statut_paiement.value]}"), h3)
    )
    if facture.mode_paiement:
        elements.append(
            Paragraph(pl.tr(f"{s['mode_paiement']} : {s['mode_labels'][facture.mode_paiement.value]}"), normal)
        )

    doc.build(elements)
    return buffer.getvalue()


def save_facture_pdf(facture: Facture) -> str:
    pdf_bytes = render_facture_pdf(facture)

    target_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "factures"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{facture.numero_facture}.pdf"
    (target_dir / filename).write_bytes(pdf_bytes)

    relative_path = f"factures/{filename}"
    facture.pdf_url = relative_path
    db.session.commit()
    return relative_path
