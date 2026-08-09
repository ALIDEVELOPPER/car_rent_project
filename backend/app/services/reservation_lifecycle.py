from app.models import Reservation
from app.models.enums import StatutReservation, StatutVehicule

ALLOWED_TRANSITIONS: dict[StatutReservation, set[StatutReservation]] = {
    StatutReservation.EN_ATTENTE: {
        StatutReservation.CONFIRMEE,
        StatutReservation.EN_COURS,
        StatutReservation.ANNULEE,
    },
    StatutReservation.CONFIRMEE: {StatutReservation.EN_COURS, StatutReservation.ANNULEE},
    StatutReservation.EN_COURS: {StatutReservation.TERMINEE, StatutReservation.ANNULEE},
    StatutReservation.TERMINEE: set(),
    StatutReservation.ANNULEE: set(),
}


class InvalidTransitionError(ValueError):
    pass


def apply_statut_transition(reservation: Reservation, nouveau_statut: StatutReservation) -> None:
    if nouveau_statut not in ALLOWED_TRANSITIONS[reservation.statut]:
        raise InvalidTransitionError(
            f"Transition {reservation.statut.value} -> {nouveau_statut.value} non autorisée"
        )

    reservation.statut = nouveau_statut

    # Le statut du véhicule ne reflète que sa disponibilité "à cet instant" ;
    # on ne l'écrase pas s'il a été mis manuellement en maintenance/hors service.
    vehicule = reservation.vehicule
    if nouveau_statut == StatutReservation.EN_COURS:
        vehicule.statut = StatutVehicule.LOUE
    elif nouveau_statut in (StatutReservation.TERMINEE, StatutReservation.ANNULEE):
        if vehicule.statut == StatutVehicule.LOUE:
            vehicule.statut = StatutVehicule.DISPONIBLE
