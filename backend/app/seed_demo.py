"""Seed local manager/member accounts without changing existing credentials."""

import logging
import os

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.db import engine, init_db
from app.models import Role, UserCreate

logger = logging.getLogger(__name__)


def seed_demo(session: Session, password: str) -> None:
    accounts = [
        UserCreate(email=f"{role}@example.com", password=password, role=role)
        for role in (Role.manager, Role.member)
    ]
    missing = []
    for account in accounts:
        existing = crud.get_user_by_email(session=session, email=account.email)
        if existing is None:
            missing.append(account)
        elif existing.role != account.role:
            raise ValueError(f"Existing account {account.email} has a different role")
    admin = crud.get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    if admin is not None and admin.role != Role.admin:
        raise ValueError(
            "The configured administrator already exists with a different role"
        )
    init_db(session)
    for account in missing:
        crud.create_user(session=session, user_create=account)
    logger.info("Demo accounts are ready; existing passwords were preserved")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    password = os.environ.get("DEMO_USER_PASSWORD")
    if not password or not 8 <= len(password) <= 128:
        raise SystemExit("Set DEMO_USER_PASSWORD (8–128 characters) before seeding")
    with Session(engine) as session:
        seed_demo(session, password)


if __name__ == "__main__":
    main()
