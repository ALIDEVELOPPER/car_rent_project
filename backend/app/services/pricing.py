from datetime import date
from decimal import Decimal


def compute_nombre_jours(date_debut: date, date_fin: date) -> int:
    nombre_jours = (date_fin - date_debut).days
    if nombre_jours <= 0:
        raise ValueError("La date de fin doit être postérieure à la date de début")
    return nombre_jours


def compute_montant_total(prix_jour: Decimal, date_debut: date, date_fin: date) -> Decimal:
    return prix_jour * compute_nombre_jours(date_debut, date_fin)
