import pytest

from tests.db import TestSessionLocal, override_get_db, test_engine
from server.database import Base, get_db
from server.auth import create_access_token
import server.main as main

main.app.dependency_overrides[get_db] = override_get_db
main.app.state.limiter.enabled = False


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture()
def client(clean_db):
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


from tests.helpers import make_user  # noqa: E402


@pytest.fixture()
def user(clean_db):
    return make_user()


@pytest.fixture()
def admin(clean_db):
    return make_user(email="admin@test.com", is_admin=True)


def auth_headers_for(u):
    token = create_access_token(data={"sub": u.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(user):
    return auth_headers_for(user)


@pytest.fixture()
def admin_headers(admin):
    return auth_headers_for(admin)
