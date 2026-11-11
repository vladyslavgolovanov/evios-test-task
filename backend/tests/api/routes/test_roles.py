from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.security import create_access_token
from app.models import Role, UserCreate
from tests.utils.utils import random_email


def headers_for(user_id: object) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(str(user_id), timedelta(minutes=5))}"
    }


@pytest.mark.parametrize("role", list(Role))
def test_user_permission_matrix(client: TestClient, db: Session, role: Role) -> None:
    actor = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password="RoleTest123!", role=role
        ),
    )
    other = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password="RoleTest123!"),
    )
    headers = headers_for(actor.id)
    can_list = role in {Role.admin, Role.manager}
    can_manage = role == Role.admin
    assert client.get("/api/v1/users/", headers=headers).status_code == (
        200 if can_list else 403
    )
    assert client.post(
        "/api/v1/users/",
        headers=headers,
        json={"email": random_email(), "password": "RoleTest123!", "role": "manager"},
    ).status_code == (200 if can_manage else 403)
    assert client.get("/api/v1/users/me", headers=headers).json()["role"] == role
    assert (
        client.patch(
            "/api/v1/users/me", headers=headers, json={"full_name": "Own profile"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/users/{other.id}", headers=headers).status_code == (
        200 if can_manage else 403
    )
    assert client.patch(
        f"/api/v1/users/{other.id}",
        headers=headers,
        json={"full_name": "Another profile"},
    ).status_code == (200 if can_manage else 403)
    assert client.delete(f"/api/v1/users/{other.id}", headers=headers).status_code == (
        200 if can_manage else 403
    )
    if not can_manage:
        db.refresh(other)
        assert other.full_name is None


def test_signup_and_own_profile_cannot_grant_privileges(client: TestClient) -> None:
    result = client.post(
        "/api/v1/users/signup",
        json={
            "email": random_email(),
            "password": "RoleTest123!",
            "role": "admin",
            "is_superuser": True,
        },
    )
    assert result.status_code == 200
    user = result.json()
    assert user["role"] == "member"
    assert user["is_superuser"] is False
    headers = headers_for(user["id"])
    result = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"role": "admin", "is_superuser": True, "full_name": "Safe name"},
    )
    assert result.status_code == 200
    assert result.json()["role"] == "member"
    assert result.json()["full_name"] == "Safe name"
    assert client.get("/api/v1/users/", headers=headers).status_code == 403


def test_admin_role_updates_validate_and_take_effect_for_existing_token(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password="RoleTest123!", role=Role.manager
        ),
    )
    headers = headers_for(user.id)
    assert client.get("/api/v1/users/", headers=headers).status_code == 200
    path = f"/api/v1/users/{user.id}"
    for invalid in [None, "owner"]:
        assert (
            client.patch(
                path, headers=superuser_token_headers, json={"role": invalid}
            ).status_code
            == 422
        )
    assert (
        client.patch(
            path, headers=superuser_token_headers, json={"role": "member"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/users/", headers=headers).status_code == 403
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "token",
    [
        None,
        "invalid",
        create_access_token("not-a-uuid", timedelta(minutes=5)),
        create_access_token(
            "00000000-0000-0000-0000-000000000001", timedelta(minutes=-1)
        ),
    ],
)
def test_unauthenticated_requests_are_401(
    client: TestClient, token: str | None
) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    assert client.get("/api/v1/users/", headers=headers).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
