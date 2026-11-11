import os
import subprocess
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings


def test_role_upgrade_preserves_existing_users_and_items() -> None:
    database = "role_migration_" + uuid.uuid4().hex
    admin_engine = create_engine(
        str(settings.DATABASE_URL), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    target = admin_engine.url.set(database=database)
    target_engine = create_engine(target, poolclass=NullPool)
    environment = {
        **os.environ,
        "DATABASE_URL": target.render_as_string(hide_password=False),
    }
    try:
        subprocess.run(
            ["alembic", "upgrade", "fe56fa70289e"],
            env=environment,
            check=True,
            capture_output=True,
        )
        admin_id, member_id, item_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with target_engine.begin() as connection:
            for user_id, superuser in [(admin_id, True), (member_id, False)]:
                connection.execute(
                    text(
                        'INSERT INTO "user" (id,email,is_active,is_superuser,hashed_password) VALUES (:id,:email,true,:admin,:hash)'
                    ),
                    {
                        "id": user_id,
                        "email": f"{user_id}@example.com",
                        "admin": superuser,
                        "hash": "retained-password-hash",
                    },
                )
            connection.execute(
                text("INSERT INTO item (id,title,owner_id) VALUES (:id,:title,:owner)"),
                {"id": item_id, "title": "Retained item", "owner": member_id},
            )
        subprocess.run(
            ["alembic", "upgrade", "head"],
            env=environment,
            check=True,
            capture_output=True,
        )
        with target_engine.connect() as connection:
            roles = dict(connection.execute(text('SELECT id,role FROM "user"')).all())
            assert roles == {admin_id: "admin", member_id: "member"}
            assert connection.execute(
                text('SELECT DISTINCT hashed_password FROM "user"')
            ).scalars().all() == ["retained-password-hash"]
            assert connection.execute(
                text("SELECT id,title,owner_id FROM item")
            ).one() == (item_id, "Retained item", member_id)
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_name='user' AND column_name='is_superuser'"
                    )
                ).scalar_one()
                == 0
            )
    finally:
        target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}"'))
        admin_engine.dispose()
