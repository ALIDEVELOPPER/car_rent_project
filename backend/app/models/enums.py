import enum


class RoleUser(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYE = "employe"


class TypePieceIdentite(str, enum.Enum):
    CNI = "cni"
    PASSEPORT = "passeport"


class Carburant(str, enum.Enum):
    ESSENCE = "essence"
    DIESEL = "diesel"
    HYBRIDE = "hybride"
    ELECTRIQUE = "electrique"


class Transmission(str, enum.Enum):
    MANUELLE = "manuelle"
    AUTOMATIQUE = "automatique"


class StatutVehicule(str, enum.Enum):
    DISPONIBLE = "disponible"
    LOUE = "loue"
    MAINTENANCE = "maintenance"
    HORS_SERVICE = "hors_service"


class StatutReservation(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    CONFIRMEE = "confirmee"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    ANNULEE = "annulee"


class StatutPaiement(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    PAYEE = "payee"
    ANNULEE = "annulee"


class ModePaiement(str, enum.Enum):
    ESPECES = "especes"
    CARTE = "carte"
    VIREMENT = "virement"
    CHEQUE = "cheque"


class StatutCaution(str, enum.Enum):
    NON_RECUE = "non_recue"
    RECUE = "recue"
    RESTITUEE = "restituee"
    RETENUE = "retenue"
