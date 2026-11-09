"""Registro de auditoría (RF-26, SEG-09): quién hizo qué y cuándo. Solo ``audit:read`` (Admin).

GET /api/v1/audit?page&page_size&category&q   -> {items, total, page, page_size}
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import SessionDep, require_permission
from app.api.v1.schemas import PageOut
from app.application.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from app.domain.permissions import Permission
from app.domain.users import User
from app.infrastructure.db.repositories import SqlAuditReader

AuditReaderUser = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]
CATEGORIES = ("auth", "users", "drivers", "passengers")

router = APIRouter(tags=["audit"])


class AuditEntryOut(BaseModel):
    action: str  # "auth.login_failed", "drivers.created"...
    occurred_at: datetime  # ISO-8601 UTC
    actor_email: str | None
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict[str, Any] | None


@router.get("/audit", response_model=PageOut[AuditEntryOut], summary="Registro de auditoría (más reciente primero)")
async def list_audit(
    _admin: AuditReaderUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    category: Annotated[str | None, Query(pattern="^(auth|users|drivers|passengers)$")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Busca por correo del actor")] = None,
) -> PageOut[AuditEntryOut]:
    request = PageRequest(page, page_size)
    entries, total = await SqlAuditReader(session).list_page(request.offset, request.page_size, category=category, search=q)
    return PageOut(
        items=[AuditEntryOut(**{k: getattr(e, k) for k in AuditEntryOut.model_fields}) for e in entries],
        total=total, page=page, page_size=page_size,
    )
