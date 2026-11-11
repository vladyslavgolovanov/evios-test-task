from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import func, select

from app.api.deps import SessionDep, require_roles
from app.models import Item, Role, User

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_roles(Role.admin, Role.manager))],
)


class Metrics(BaseModel):
    users: int
    items: int


@router.get("/")
def read_metrics(session: SessionDep) -> Metrics:
    return Metrics(
        users=session.exec(select(func.count()).select_from(User)).one(),
        items=session.exec(select(func.count()).select_from(Item)).one(),
    )
