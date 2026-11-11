import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.models import Item, Role, User, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email


@pytest.mark.parametrize("role", list(Role))
def test_metrics_permission_and_counts(
    client: TestClient, db: Session, role: Role
) -> None:
    email, password = random_email(), "Metrics-test-123!"
    crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password, role=role)
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    response = client.get("/api/v1/metrics/", headers=headers)
    if role == Role.member:
        assert response.status_code == 403
    else:
        assert response.status_code == 200
        assert response.json() == {
            "users": db.exec(select(func.count()).select_from(User)).one(),
            "items": db.exec(select(func.count()).select_from(Item)).one(),
        }


def test_metrics_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/metrics/").status_code == 401
