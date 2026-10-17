"""Admin settings backed by the singleton row; changes are audited atomically."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.schemas import SettingsOut, UpdateSettingsIn
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.security import require_roles
from app.core.sla import SlaNotConfigured, get_settings_row, sla_unavailable
from app.models import User
from app.models.role import utc_now


router = APIRouter(tags=["settings"])
ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "text/plain"}


def _row(session: Session):
    try:
        return get_settings_row(session)
    except SlaNotConfigured:
        raise sla_unavailable() from None


@router.get("/settings", response_model=SettingsOut, summary="Read system settings")
def read_settings(
    _: User = Depends(require_roles("Admin")),
    session: Session = Depends(get_db),
) -> SettingsOut:
    return SettingsOut.from_settings(_row(session))


@router.patch("/settings", response_model=SettingsOut, summary="Update system settings")
def update_settings(
    data: UpdateSettingsIn,
    actor: User = Depends(require_roles("Admin")),
    session: Session = Depends(get_db),
) -> SettingsOut:
    settings = _row(session)
    changes = data.model_dump(exclude_unset=True)
    if "max_attachment_bytes" in changes and changes["max_attachment_bytes"] <= 0:
        raise HTTPException(status_code=400, detail="Attachment limit must be positive")
    if "allowed_attachment_types" in changes:
        types = changes["allowed_attachment_types"]
        if not types or len(types) != len(set(types)) or not set(types) <= ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Invalid allowed attachment types")
    if "sla_targets" in changes:
        for target in changes["sla_targets"].values():
            if (target["first_response_hours"] <= 0 or target["resolution_hours"] <= 0
                    or target["first_response_hours"] > target["resolution_hours"]):
                raise HTTPException(status_code=400, detail="Invalid SLA targets")
    old = {key: getattr(settings, key) for key in changes}
    if old != changes:
        for key, value in changes.items():
            setattr(settings, key, value)
        settings.updated_at = utc_now()
        record_audit(
            session, actor_id=actor.id, action="settings_update",
            entity_type="settings", entity_id=settings.id,
            old_value=old, new_value=changes,
        )
    session.commit()
    return SettingsOut.from_settings(settings)
