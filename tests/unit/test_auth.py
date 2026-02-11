from app.models import User
from app.extensions import bcrypt, db


def test_register_creates_user_and_logs_in(client, app):
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Test Collector",
            "email": "collector@example.com",
            "password": "hunter2026",
            "confirm_password": "hunter2026",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Dashboard" in response.data

    with app.app_context():
        user = User.query.filter_by(email="collector@example.com").first()
        assert user is not None
        assert user.display_name == "Test Collector"


def test_login_rejects_invalid_credentials(client, app):
    with app.app_context():
        user = User(username="collector", email="collector@example.com")
        user.set_password("hunter2026", bcrypt)
        user.is_verified = True
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={"email": "collector@example.com", "password": "wrongpass123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_accepts_valid_credentials(client, app):
    with app.app_context():
        user = User(username="collector", email="collector@example.com")
        user.set_password("hunter2026", bcrypt)
        user.is_verified = True
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={"email": "collector@example.com", "password": "hunter2026"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_duplicate_email_registration_shows_error(client, app):
    with app.app_context():
        user = User(username="collector", email="collector@example.com")
        user.set_password("hunter2026", bcrypt)
        user.is_verified = True
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/register",
        data={
            "full_name": "Second Collector",
            "email": "collector@example.com",
            "password": "hunter2026",
            "confirm_password": "hunter2026",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_dashboard_redirects_anonymous_users_to_login(client):
    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_signs_out_authenticated_user(client):
    client.post(
        "/auth/register",
        data={
            "full_name": "Test Collector",
            "email": "collector@example.com",
            "password": "hunter2026",
            "confirm_password": "hunter2026",
        },
        follow_redirects=True,
    )

    response = client.post("/auth/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"Signed out" in response.data
