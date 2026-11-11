import pytest
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.security import verify_password
from app.models import Role
from app.seed_demo import seed_demo


def test_seed_creates_roles_and_preserves_credentials_on_repeat(db: Session) -> None:
    seed_demo(db, "First-demo-password")
    original = {}
    for role in (Role.manager, Role.member):
        user = crud.get_user_by_email(session=db, email=f"{role}@example.com")
        assert user is not None and user.role == role
        assert verify_password("First-demo-password", user.hashed_password)[0]
        original[role] = (user.id, user.hashed_password)
    seed_demo(db, "Different-demo-password")
    for role, expected in original.items():
        user = crud.get_user_by_email(session=db, email=f"{role}@example.com")
        assert user is not None
        assert (user.id, user.hashed_password) == expected
    admin = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert admin is not None and admin.role == Role.admin


def test_seed_refuses_to_change_an_existing_accounts_role(db: Session) -> None:
    seed_demo(db, "First-demo-password")
    user = crud.get_user_by_email(session=db, email="manager@example.com")
    assert user is not None
    user.role = Role.member
    db.add(user)
    db.commit()
    try:
        with pytest.raises(ValueError, match="different role"):
            seed_demo(db, "Replacement-password")
        db.refresh(user)
        assert user.role == Role.member
        assert verify_password("First-demo-password", user.hashed_password)[0]
    finally:
        user.role = Role.manager
        db.add(user)
        db.commit()
