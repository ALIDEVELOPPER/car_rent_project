"""Génération du contrat de location de véhicule au format PDF.

Le contrat est le document signé à la remise des clés (distinct de la facture).
Textes regroupés en tête pour faciliter la traduction (arabe) à venir.
"""
import io

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.enums import StatutReservation
from app.services.agence import get_or_create_agence

CONDITIONS_PAR_DEFAUT = (
    "1. Le locataire reconnaît avoir reçu le véhicule en bon état de marche, avec ses "
    "accessoires et documents de bord.\n"
    "2. Le véhicule ne peut être conduit que par le locataire ou un conducteur "
    "désigné au contrat, titulaire d'un permis de conduire valide depuis plus d'un an.\n"
    "3. Il est interdit de sous-louer le véhicule, de l'utiliser pour le transport "
    "rémunéré de personnes ou de marchandises, ou de participer à des compétitions.\n"
    "4. Le carburant est à la charge du locataire. Le véhicule est restitué avec le "
    "même niveau de carburant qu'au départ.\n"
    "5. Toute prolongation doit faire l'objet d'un accord écrit de l'agence. Tout "
    "retard de restitution non signalé est facturé au tarif journalier majoré.\n"
    "6. Les contraventions et amendes sont à la charge du locataire.\n"
    "7. En cas d'accident, le locataire doit prévenir immédiatement l'agence et "
    "établir un constat. La caution reste acquise à l'agence jusqu'à règlement du "
    "sinistre.\n"
    "8. La caution est restituée après vérification de l'état du véhicule et du "
    "kilométrage."
)

L = {
    "titre": "CONTRAT DE LOCATION DE VÉHICULE",
    "numero": "Contrat N°",
    "date_edition": "Établi le",
    "loc_section": "LE LOCATAIRE",
    "veh_section": "LE VÉHICULE",
    "location_section": "LA LOCATION",
    "conditions_section": "CONDITIONS GÉNÉRALES",
    "nom": "Nom et prénom",
    "cin": "Pièce d'identité n°",
    "permis": "Permis de conduire n°",
    "permis_date": "délivré le",
    "naissance": "Date de naissance",
    "adresse": "Adresse",
    "tel": "Téléphone",
    "email": "E-mail",
    "vehicule": "Véhicule",
    "immat": "Immatriculation",
    "annee": "Année",
    "couleur": "Couleur",
    "carburant": "Carburant",
    "km_depart": "Kilométrage au départ",
    "km_retour": "Kilométrage au retour",
    "du": "Du",
    "au": "au",
    "periode": "Période",
    "jours_unite": "jours",
    "lieu": "Lieu de prise en charge",
    "prix_jour": "Prix par jour",
    "total": "Montant total",
    "caution": "Caution (dépôt de garantie)",
    "heure_depart": "Heure de départ",
    "heure_retour": "Heure de retour",
    "carburant_depart": "Niveau carburant départ",
    "carburant_retour": "Niveau carburant retour",
    "a_remplir": "À remplir à la restitution",
    "sign_locataire": "Signature du locataire",
    "sign_agence": "Pour l'agence",
    "lu_approuve": "(précédée de la mention « Lu et approuvé »)",
    "fait_a": "Fait à ………………………………, le ……… / ……… / ………………",
}


def _fmt_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "……………………"


def _fmt_money(value, devise: str) -> str:
    if value is None:
        return "……………………"
    return f"{value} {devise}"


def render_contrat_pdf(reservation) -> bytes:
    client = reservation.client
    vehicule = reservation.vehicule
    agence = get_or_create_agence()
    devise = current_app.config["CURRENCY_LABEL"]

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontSize = 9
    normal.leading = 13
    petit = ParagraphStyle("petit", parent=normal, fontSize=7.5, textColor=colors.HexColor("#555555"))
    section_style = ParagraphStyle(
        "section", parent=styles["Heading3"], fontSize=10, spaceBefore=10, spaceAfter=4,
        textColor=colors.HexColor("#1e293b"),
    )
    cg_style = ParagraphStyle("cg", parent=normal, fontSize=7.5, leading=10, alignment=TA_JUSTIFY)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm, title="Contrat de location",
    )

    elements = []

    # --- En-tête agence ---
    entete = [Paragraph(f"<b>{agence.nom}</b>", ParagraphStyle("h", parent=normal, fontSize=13))]
    if agence.adresse:
        entete.append(Paragraph(agence.adresse, normal))
    contact = " · ".join(filter(None, [agence.telephone, agence.email]))
    if contact:
        entete.append(Paragraph(contact, normal))
    if agence.mentions_legales:
        entete.append(Paragraph(agence.mentions_legales.replace("\n", "<br/>"), petit))
    elements.append(Table([[entete]], colWidths=[doc.width]))
    elements.append(Spacer(1, 0.3 * cm))

    elements.append(
        Paragraph(f"<b>{L['titre']}</b>", ParagraphStyle("t", parent=normal, fontSize=14, alignment=1))
    )
    elements.append(
        Paragraph(
            f"{L['numero']} {reservation.id:05d}    —    {L['date_edition']} {_fmt_date(reservation.created_at)}",
            ParagraphStyle("sub", parent=normal, alignment=1, textColor=colors.HexColor("#555555")),
        )
    )
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")))

    def kv_table(rows):
        t = Table(rows, colWidths=[doc.width * 0.28, doc.width * 0.72])
        t.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    # --- Locataire ---
    elements.append(Paragraph(L["loc_section"], section_style))
    piece = client.numero_piece_identite or "……………………"
    if client.type_piece_identite:
        piece = f"{piece} ({client.type_piece_identite.value})"
    elements.append(
        kv_table(
            [
                [L["nom"], f"{client.prenom} {client.nom}"],
                [L["cin"], piece],
                [L["permis"], f"{client.numero_permis or '……………………'}   {L['permis_date']} {_fmt_date(client.date_delivrance_permis)}"],
                [L["naissance"], _fmt_date(client.date_naissance)],
                [L["adresse"], client.adresse or "……………………"],
                [L["tel"], client.telephone or "……………………"],
                [L["email"], client.email or "……………………"],
            ]
        )
    )

    # --- Véhicule ---
    elements.append(Paragraph(L["veh_section"], section_style))
    elements.append(
        kv_table(
            [
                [L["vehicule"], f"{vehicule.marque} {vehicule.modele}"],
                [L["immat"], vehicule.immatriculation],
                [L["annee"], str(vehicule.annee) if vehicule.annee else "……………………"],
                [L["couleur"], vehicule.couleur or "……………………"],
                [L["carburant"], vehicule.carburant.value if vehicule.carburant else "……………………"],
                [L["km_depart"], str(vehicule.kilometrage) if vehicule.kilometrage is not None else "……………………"],
            ]
        )
    )

    # --- Location ---
    nb_jours = (reservation.date_fin - reservation.date_debut).days
    elements.append(Paragraph(L["location_section"], section_style))
    elements.append(
        kv_table(
            [
                [L["periode"], f"{L['du']} {_fmt_date(reservation.date_debut)} {L['au']} {_fmt_date(reservation.date_fin)}  ({nb_jours} {L['jours_unite']})"],
                [L["lieu"], reservation.lieu_prise_en_charge or "……………………"],
                [L["prix_jour"], _fmt_money(reservation.prix_jour_applique, devise)],
                [L["total"], _fmt_money(reservation.montant_total, devise)],
                [L["caution"], _fmt_money(reservation.caution, devise)],
            ]
        )
    )

    # --- Cases à remplir à la restitution ---
    a_remplir = Table(
        [
            [f"{L['heure_depart']} : ……………", f"{L['heure_retour']} : ……………", f"{L['km_retour']} : ……………………"],
            [f"{L['carburant_depart']} : ……………", f"{L['carburant_retour']} : ……………", ""],
        ],
        colWidths=[doc.width / 3] * 3,
    )
    a_remplir.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(L["a_remplir"], petit))
    elements.append(a_remplir)

    # --- Conditions générales ---
    conditions = agence.conditions_contrat or CONDITIONS_PAR_DEFAUT
    cg_flowables = [Paragraph(L["conditions_section"], section_style)]
    for ligne in conditions.split("\n"):
        ligne = ligne.strip()
        if ligne:
            cg_flowables.append(Paragraph(ligne, cg_style))
    elements.append(KeepTogether(cg_flowables))

    # --- Signatures --- (gardé sur une seule page)
    sign = Table(
        [
            [L["sign_locataire"], L["sign_agence"]],
            [L["lu_approuve"], ""],
            ["", ""],
        ],
        colWidths=[doc.width / 2] * 2,
        rowHeights=[0.5 * cm, 0.4 * cm, 1.8 * cm],
    )
    sign.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 7),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#777777")),
                ("LINEBELOW", (0, 2), (0, 2), 0.5, colors.HexColor("#333333")),
                ("LINEBELOW", (1, 2), (1, 2), 0.5, colors.HexColor("#333333")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(
        KeepTogether([Spacer(1, 0.5 * cm), Paragraph(L["fait_a"], normal), Spacer(1, 0.3 * cm), sign])
    )

    doc.build(elements)
    return buffer.getvalue()


def contrat_disponible(reservation) -> bool:
    return reservation.statut != StatutReservation.ANNULEE
