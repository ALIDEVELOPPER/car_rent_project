from app.extensions import db
from app.models import Agence


def get_or_create_agence() -> Agence:
    agence = db.session.execute(db.select(Agence)).scalars().first()
    if agence is None:
        agence = Agence(nom="Mon Agence de Location")
        db.session.add(agence)
        db.session.commit()
    return agence
