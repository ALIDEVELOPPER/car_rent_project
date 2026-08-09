from datetime import date

from app.extensions import db
from app.models import Reservation
from app.models.enums import StatutReservation

# Une réservation annulée libère les dates ; toutes les autres les bloquent
# (y compris "terminée", pour l'intégrité de l'historique — sans effet pratique
# puisque ses dates sont déjà passées).
BLOCKING_STATUTS = {
    StatutReservation.EN_ATTENTE,
    StatutReservation.CONFIRMEE,
    StatutReservation.EN_COURS,
    StatutReservation.TERMINEE,
}


def is_vehicule_available(
    vehicule_id: int,
    date_debut: date,
    date_fin: date,
    exclude_reservation_id: int | None = None,
) -> bool:
    # Chevauchement strict : la date de fin d'une réservation peut coïncider avec
    # la date de début d'une autre (rotation le même jour autorisée).
    query = db.select(Reservation.id).filter(
        Reservation.vehicule_id == vehicule_id,
        Reservation.statut.in_(BLOCKING_STATUTS),
        Reservation.date_debut < date_fin,
        Reservation.date_fin > date_debut,
    )
    if exclude_reservation_id is not None:
        query = query.filter(Reservation.id != exclude_reservation_id)

    conflict = db.session.execute(query.limit(1)).scalar_one_or_none()
    return conflict is None
