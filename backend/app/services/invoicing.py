import io
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.extensions import db
from app.models import Facture, Reservation
from app.models.enums import ModePaiement, StatutPaiement
from app.services.agence import get_or_create_agence

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
    facture = Facture(
        reservation_id=reservation.id,
        numero_facture=_generate_numero_facture(now.year),
        date_emission=now,
        montant=reservation.montant_total,
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


def render_facture_pdf(facture: Facture) -> bytes:
    reservation = facture.reservation
    client_obj = reservation.client
    vehicule = reservation.vehicule
    agence = _get_agence_info()
    devise = current_app.config["CURRENCY_LABEL"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titre_agence_style = ParagraphStyle("TitreAgence", parent=styles["Heading1"], fontSize=16)

    elements = [Paragraph(agence["nom"], titre_agence_style)]
    if agence["adresse"]:
        elements.append(Paragraph(agence["adresse"], styles["Normal"]))
    contact_line = " · ".join(filter(None, [agence["telephone"], agence["email"]]))
    if contact_line:
        elements.append(Paragraph(contact_line, styles["Normal"]))
    elements.append(Spacer(1, 1 * cm))

    elements.append(Paragraph(f"Facture {facture.numero_facture}", styles["Heading2"]))
    elements.append(
        Paragraph(f"Date d'émission : {facture.date_emission.strftime('%d/%m/%Y')}", styles["Normal"])
    )
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Client", styles["Heading3"]))
    elements.append(Paragraph(f"{client_obj.prenom} {client_obj.nom}", styles["Normal"]))
    if client_obj.telephone:
        elements.append(Paragraph(client_obj.telephone, styles["Normal"]))
    if client_obj.email:
        elements.append(Paragraph(client_obj.email, styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    nombre_jours = (reservation.date_fin - reservation.date_debut).days
    table_data = [
        ["Véhicule", "Période", "Jours", f"Prix / jour ({devise})", f"Montant ({devise})"],
        [
            f"{vehicule.marque} {vehicule.modele} ({vehicule.immatriculation})",
            f"{reservation.date_debut.strftime('%d/%m/%Y')} - {reservation.date_fin.strftime('%d/%m/%Y')}",
            str(nombre_jours),
            f"{reservation.prix_jour_applique}",
            f"{facture.montant}",
        ],
    ]
    table = Table(table_data, colWidths=[5 * cm, 4.5 * cm, 1.5 * cm, 3 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 1 * cm))

    statut_labels = {
        StatutPaiement.EN_ATTENTE: "En attente de paiement",
        StatutPaiement.PAYEE: "Payée",
        StatutPaiement.ANNULEE: "Annulée",
    }
    elements.append(Paragraph(f"Statut : {statut_labels[facture.statut_paiement]}", styles["Heading3"]))
    if facture.mode_paiement:
        elements.append(Paragraph(f"Mode de paiement : {facture.mode_paiement.value}", styles["Normal"]))

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
