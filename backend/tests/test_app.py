from app.models import User


def test_app_creates_in_testing_mode(app):
    assert app.config["TESTING"] is True


def test_database_is_usable(app, db):
    user = User(nom="Test", email="test@example.com", role="admin")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    fetched = db.session.get(User, user.id)
    assert fetched.email == "test@example.com"
    assert fetched.check_password("secret123")
    assert not fetched.check_password("wrong")
