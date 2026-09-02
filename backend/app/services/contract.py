"""Génération du contrat de location de véhicule au format PDF (français / arabe).

Le contrat est le document signé à la remise des clés (distinct de la facture).
La langue suit celle choisie dans les paramètres de l'agence.
"""
import io
import re

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
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
from app.services.pdf_i18n import PdfLang

CONDITIONS_PAR_DEFAUT = {
    "fr": (
        "1. Le locataire reconnaît avoir reçu le véhicule en bon état de marche, avec ses "
        "accessoires et documents de bord.\n"
        "2. Le véhicule ne peut être conduit que par le locataire ou un conducteur désigné au "
        "contrat, titulaire d'un permis de conduire valide depuis plus d'un an.\n"
        "3. Il est interdit de sous-louer le véhicule, de l'utiliser pour le transport rémunéré "
        "de personnes ou de marchandises, ou de participer à des compétitions.\n"
        "4. Le carburant est à la charge du locataire. Le véhicule est restitué avec le même "
        "niveau de carburant qu'au départ.\n"
        "5. Toute prolongation doit faire l'objet d'un accord écrit de l'agence. Tout retard de "
        "restitution non signalé est facturé au tarif journalier majoré.\n"
        "6. Les contraventions et amendes sont à la charge du locataire.\n"
        "7. En cas d'accident, le locataire doit prévenir immédiatement l'agence et établir un "
        "constat. La caution reste acquise à l'agence jusqu'à règlement du sinistre.\n"
        "8. La caution est restituée après vérification de l'état du véhicule et du kilométrage."
    ),
    "ar": (
        "1. يقر المكتري بأنه تسلم السيارة في حالة جيدة للسير، مع ملحقاتها ووثائق متنها.\n"
        "2. لا يحق قيادة السيارة إلا للمكتري أو لسائق مصرَّح به في العقد، حائز على رخصة سياقة "
        "صالحة منذ أكثر من سنة.\n"
        "3. يُمنع كراء السيارة من الباطن، أو استعمالها لنقل الأشخاص أو البضائع بمقابل، أو "
        "المشاركة بها في السباقات.\n"
        "4. الوقود على نفقة المكتري. تُرجَع السيارة بنفس مستوى الوقود الذي كانت عليه عند "
        "الانطلاق.\n"
        "5. كل تمديد يجب أن يكون بموافقة كتابية من الوكالة. كل تأخير في الإرجاع غير مُبلَّغ عنه "
        "يُفوتر بالثمن اليومي مع زيادة.\n"
        "6. المخالفات والغرامات على عاتق المكتري.\n"
        "7. في حالة وقوع حادثة، يجب على المكتري إشعار الوكالة فورًا وتحرير محضر معاينة. تبقى "
        "الضمانة محتجزة لدى الوكالة إلى حين تسوية الحادث.\n"
        "8. تُرجَع الضمانة بعد التحقق من حالة السيارة وعدد الكيلومترات."
    ),
}

STR = {
    "fr": {
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
        "periode": "Période",
        "du": "Du",
        "au": "au",
        "jours_unite": "jours",
        "lieu": "Lieu de prise en charge",
        "prix_jour": "Prix par jour",
        "total": "Montant total",
        "caution": "Caution (dépôt de garantie)",
        "caution_statut": {
            "non_recue": "non reçue", "recue": "reçue", "restituee": "restituée", "retenue": "retenue",
        },
        "heure_depart": "Heure de départ",
        "heure_retour": "Heure de retour",
        "carburant_depart": "Niveau carburant départ",
        "carburant_retour": "Niveau carburant retour",
        "a_remplir": "À remplir à la restitution",
        "sign_locataire": "Signature du locataire",
        "sign_agence": "Pour l'agence",
        "lu_approuve": "(précédée de la mention « Lu et approuvé »)",
        "fait_a": "Fait à ………………………………, le ……… / ……… / ………………",
        "devise": "MAD",
    },
    "ar": {
        "titre": "عقد كراء سيارة",
        "numero": "عقد رقم",
        "date_edition": "حُرِّر في",
        "loc_section": "المُكتري",
        "veh_section": "السيارة",
        "location_section": "الكراء",
        "conditions_section": "الشروط العامة",
        "nom": "الاسم الكامل",
        "cin": "رقم بطاقة الهوية",
        "permis": "رقم رخصة السياقة",
        "permis_date": "مُسلَّمة في",
        "naissance": "تاريخ الازدياد",
        "adresse": "العنوان",
        "tel": "الهاتف",
        "email": "البريد الإلكتروني",
        "vehicule": "السيارة",
        "immat": "رقم التسجيل",
        "annee": "السنة",
        "couleur": "اللون",
        "carburant": "الوقود",
        "km_depart": "عدد الكيلومترات عند الانطلاق",
        "km_retour": "عدد الكيلومترات عند الإرجاع",
        "periode": "المدة",
        "du": "من",
        "au": "إلى",
        "jours_unite": "أيام",
        "lieu": "مكان التسليم",
        "prix_jour": "الثمن اليومي",
        "total": "المبلغ الإجمالي",
        "caution": "الضمانة (مبلغ التأمين)",
        "caution_statut": {
            "non_recue": "غير مستلمة", "recue": "مستلمة", "restituee": "مُرجَعة", "retenue": "محتجزة",
        },
        "heure_depart": "ساعة الانطلاق",
        "heure_retour": "ساعة الإرجاع",
        "carburant_depart": "مستوى الوقود عند الانطلاق",
        "carburant_retour": "مستوى الوقود عند الإرجاع",
        "a_remplir": "يُملأ عند الإرجاع",
        "sign_locataire": "توقيع المكتري",
        "sign_agence": "عن الوكالة",
        "lu_approuve": "(مسبوقًا بعبارة «قُرئ وصودق عليه»)",
        "fait_a": "حُرِّر بـ ……………………، بتاريخ ……… / ……… / ………………",
        "devise": "درهم",
    },
}

_BLANK = "……………………"


def _fmt_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else _BLANK


def _fmt_money(value, devise: str) -> str:
    return f"{value} {devise}" if value is not None else _BLANK


def render_contrat_pdf(reservation) -> bytes:
    client = reservation.client
    vehicule = reservation.vehicule
    agence = get_or_create_agence()
    pl = PdfLang(agence.langue)
    s = STR[pl.lang]
    devise = "درهم" if pl.rtl else current_app.config["CURRENCY_LABEL"]

    normal = ParagraphStyle("n", fontName=pl.font, fontSize=9, leading=13, alignment=pl.align)
    petit = ParagraphStyle("p", parent=normal, fontSize=7.5, textColor=colors.HexColor("#555555"))
    section_style = ParagraphStyle(
        "s", fontName=pl.font_bold, fontSize=10, spaceBefore=10, spaceAfter=4,
        alignment=pl.align, textColor=colors.HexColor("#1e293b"),
    )
    cg_style = ParagraphStyle("cg", parent=normal, fontSize=7.5, leading=11, alignment=pl.align)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm, title="Contrat de location",
    )

    elements = []

    entete = [Paragraph(f"<b>{pl.tr(agence.nom)}</b>", ParagraphStyle("h", parent=normal, fontSize=13))]
    if agence.adresse:
        entete.append(Paragraph(pl.tr(agence.adresse), normal))
    contact = " · ".join(filter(None, [agence.telephone, agence.email]))
    if contact:
        entete.append(Paragraph(pl.tr(contact), normal))
    if agence.mentions_legales:
        entete.append(Paragraph(pl.wrap(agence.mentions_legales.replace("\n", " ")), petit))
    elements.append(Table([[entete]], colWidths=[doc.width]))
    elements.append(Spacer(1, 0.3 * cm))

    elements.append(
        Paragraph(f"<b>{pl.tr(s['titre'])}</b>", ParagraphStyle("t", fontName=pl.font_bold, fontSize=14, alignment=1))
    )
    elements.append(
        Paragraph(
            pl.tr(f"{s['numero']} {reservation.id:05d}    —    {s['date_edition']} {_fmt_date(reservation.created_at)}"),
            ParagraphStyle("sub", parent=normal, alignment=1, textColor=colors.HexColor("#555555")),
        )
    )
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")))

    def kv_table(pairs):
        rows = [pl.kv(label, value) for label, value in pairs]
        label_w, value_w = doc.width * 0.28, doc.width * 0.72
        col_widths = [value_w, label_w] if pl.rtl else [label_w, value_w]
        t = Table(rows, colWidths=col_widths)
        label_col = 1 if pl.rtl else 0
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), pl.font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TEXTCOLOR", (label_col, 0), (label_col, -1), colors.HexColor("#555555")),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    piece = client.numero_piece_identite or _BLANK
    if client.type_piece_identite:
        piece = f"{piece} ({client.type_piece_identite.value})"

    elements.append(Paragraph(pl.tr(s["loc_section"]), section_style))
    elements.append(
        kv_table(
            [
                (s["nom"], f"{client.prenom} {client.nom}"),
                (s["cin"], piece),
                (s["permis"], f"{client.numero_permis or _BLANK}   {s['permis_date']} {_fmt_date(client.date_delivrance_permis)}"),
                (s["naissance"], _fmt_date(client.date_naissance)),
                (s["adresse"], client.adresse or _BLANK),
                (s["tel"], client.telephone or _BLANK),
                (s["email"], client.email or _BLANK),
            ]
        )
    )

    elements.append(Paragraph(pl.tr(s["veh_section"]), section_style))
    elements.append(
        kv_table(
            [
                (s["vehicule"], f"{vehicule.marque} {vehicule.modele}"),
                (s["immat"], vehicule.immatriculation),
                (s["annee"], str(vehicule.annee) if vehicule.annee else _BLANK),
                (s["couleur"], vehicule.couleur or _BLANK),
                (s["carburant"], vehicule.carburant.value if vehicule.carburant else _BLANK),
                (s["km_depart"], str(vehicule.kilometrage) if vehicule.kilometrage is not None else _BLANK),
            ]
        )
    )

    nb_jours = (reservation.date_fin - reservation.date_debut).days
    elements.append(Paragraph(pl.tr(s["location_section"]), section_style))
    elements.append(
        kv_table(
            [
                (s["periode"], f"{s['du']} {_fmt_date(reservation.date_debut)} {s['au']} {_fmt_date(reservation.date_fin)}  ({nb_jours} {s['jours_unite']})"),
                (s["lieu"], reservation.lieu_prise_en_charge or _BLANK),
                (s["prix_jour"], _fmt_money(reservation.prix_jour_applique, devise)),
                (s["total"], _fmt_money(reservation.montant_total, devise)),
                (s["caution"], f"{_fmt_money(reservation.caution, devise)}  ({s['caution_statut'][reservation.caution_statut.value]})"),
            ]
        )
    )

    remplir_cells = [
        f"{s['heure_depart']} : ……………",
        f"{s['heure_retour']} : ……………",
        f"{s['km_retour']} : ……………………",
    ]
    remplir_cells2 = [f"{s['carburant_depart']} : ……………", f"{s['carburant_retour']} : ……………", ""]
    if pl.rtl:
        remplir_cells = [pl.tr(c) for c in reversed(remplir_cells)]
        remplir_cells2 = [pl.tr(c) for c in reversed(remplir_cells2)]
    a_remplir = Table([remplir_cells, remplir_cells2], colWidths=[doc.width / 3] * 3)
    a_remplir.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), pl.font),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(pl.tr(s["a_remplir"]), petit))
    elements.append(a_remplir)

    conditions = agence.conditions_contrat or CONDITIONS_PAR_DEFAUT[pl.lang]
    cg_flowables = [Paragraph(pl.tr(s["conditions_section"]), section_style)]
    for ligne in conditions.split("\n"):
        ligne = ligne.strip()
        if not ligne:
            continue
        if pl.rtl:
            # Garde un numéro de clause "1." à l'endroit (marque LTR) en tête de ligne RTL.
            ligne = re.sub(r"^(\d+[.)])\s*", "‎\\1‏ ", ligne)
        cg_flowables.append(Paragraph(pl.wrap(ligne), cg_style))
    elements.append(KeepTogether(cg_flowables))

    sign_row1 = [s["sign_locataire"], s["sign_agence"]]
    sign_row2 = [s["lu_approuve"], ""]
    if pl.rtl:
        sign_row1 = [pl.tr(c) for c in reversed(sign_row1)]
        sign_row2 = [pl.tr(c) for c in reversed(sign_row2)]
    sign = Table(
        [sign_row1, sign_row2, ["", ""]],
        colWidths=[doc.width / 2] * 2,
        rowHeights=[0.5 * cm, 0.4 * cm, 1.8 * cm],
    )
    sign.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), pl.font),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 7),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if pl.rtl else "LEFT"),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#777777")),
                ("LINEBELOW", (0, 2), (0, 2), 0.5, colors.HexColor("#333333")),
                ("LINEBELOW", (1, 2), (1, 2), 0.5, colors.HexColor("#333333")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(
        KeepTogether([Spacer(1, 0.5 * cm), Paragraph(pl.tr(s["fait_a"]), normal), Spacer(1, 0.3 * cm), sign])
    )

    doc.build(elements)
    return buffer.getvalue()


def contrat_disponible(reservation) -> bool:
    return reservation.statut != StatutReservation.ANNULEE
