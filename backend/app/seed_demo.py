"""Opt-in, repeatable local demo data. Run with ``python -m app.seed_demo``.

No real names, addresses, or passwords live in this file. Stable UUIDs identify
only our own demo rows. Reruns add missing rows and never reset existing ones.
"""

from datetime import datetime, timedelta, timezone
from getpass import getpass
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.passwords import hash_password
from app.models import Category, Role, SystemSetting, Ticket, User


ROLE_NAMES = ("Employee", "Support agent", "Admin")
USER_SPECS = (
    ("employee", "Demo Employee", "Employee"),
    ("agent", "Demo Support Agent", "Support agent"),
    ("admin", "Demo Administrator", "Admin"),
)
CATEGORY_SPECS = (
    ("hardware", "Hardware", "Laptops and peripherals"),
    ("software", "Software", "Applications and accounts"),
    ("network", "Network", "Connectivity and VPN"),
)
# A sample of each lifecycle state. These are synthetic snapshots, not API
# actions; real ticket changes will create history and audit rows in T01/T02.
TICKET_SPECS = (
    ("open", "Laptop display flickers", "hardware", "Open", "Medium", 1,
     False, None, None),
    ("assigned", "VPN cannot connect", "network", "Assigned", "High", 5,
     True, None, None),
    ("in_progress", "Software install needs approval", "software", "In Progress",
     "Medium", 8, True, 1, None),
    ("resolved", "Printer was offline", "hardware", "Resolved", "Low", 30,
     True, 2, 18),
    ("closed", "Account access restored", "software", "Closed", "Medium", 60,
     True, 2, 24),
)


def _demo_id(seed_key: str, kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"itsm-helpdesk:{seed_key}:{kind}:{key}")


def _collision(session: Session, model: type, row_id: UUID, field, value: str) -> None:
    """Fail rather than claim a user's existing record as demo data."""
    by_id = session.get(model, row_id)
    if by_id is not None and getattr(by_id, field.key) != value:
        raise ValueError(f"Demo ID collision in {model.__tablename__}; no rows changed")
    by_key = session.scalar(select(model).where(field == value))
    if by_key is not None and by_key.id != row_id:
        raise ValueError(f"Demo {field.key} already belongs to another row; no rows changed")


def seed_demo(session: Session, password: str, *, seed_key: str = "demo") -> dict[str, int]:
    """Add demo rows once. Caller owns commit/rollback; never overwrite a row."""
    if (
        not seed_key
        or not seed_key.isascii()
        or seed_key != seed_key.lower()
        or len(seed_key) > 32
        or not seed_key.replace("-", "").isalnum()
    ):
        raise ValueError(
            "seed_key must be at most 32 lowercase ASCII letters, digits, or hyphens"
        )
    if not password or not password.strip():
        raise ValueError("Demo password must not be blank")

    now = datetime.now(timezone.utc)
    created = {"roles": 0, "users": 0, "categories": 0, "tickets": 0}
    roles: dict[str, Role] = {}
    for name in ROLE_NAMES:
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, created_at=now, updated_at=now)
            session.add(role)
            created["roles"] += 1
        roles[name] = role
    session.flush()

    users: dict[str, User] = {}
    for key, name, role_name in USER_SPECS:
        row_id = _demo_id(seed_key, "user", key)
        email = f"{seed_key}.{key}@example.test"
        _collision(session, User, row_id, User.email, email)
        user = session.get(User, row_id)
        if user is None:
            user = User(
                id=row_id, role_id=roles[role_name].id, name=name, email=email,
                password_hash=hash_password(password), is_active=True,
                created_at=now, updated_at=now,
            )
            session.add(user)
            created["users"] += 1
        users[key] = user

    categories: dict[str, Category] = {}
    for key, label, description in CATEGORY_SPECS:
        row_id = _demo_id(seed_key, "category", key)
        name = f"[{seed_key}] {label}"
        _collision(session, Category, row_id, Category.name, name)
        category = session.get(Category, row_id)
        if category is None:
            category = Category(
                id=row_id, name=name, description=description,
                is_active=True, created_at=now, updated_at=now,
            )
            session.add(category)
            created["categories"] += 1
        categories[key] = category
    session.flush()

    settings = session.scalar(
        select(SystemSetting).where(SystemSetting.is_singleton.is_(True))
    )
    if settings is None:
        raise RuntimeError("System settings are missing; run alembic upgrade head first")
    for (
        key, title, category_key, status, priority, age_hours,
        assigned, response_hours, resolution_hours,
    ) in TICKET_SPECS:
        row_id = _demo_id(seed_key, "ticket", key)
        existing = session.get(Ticket, row_id)
        if existing is not None:
            if existing.creator_id != users["employee"].id:
                raise ValueError("Demo ticket ID collision; no rows changed")
            continue
        target = settings.sla_targets.get(priority)
        if not isinstance(target, dict):
            raise ValueError(f"Missing SLA targets for {priority}")
        created_at = now - timedelta(hours=age_hours)
        session.add(Ticket(
            id=row_id,
            title=f"[{seed_key}] {title}",
            description=f"Synthetic {category_key} support request for the local demo.",
            category_id=categories[category_key].id,
            creator_id=users["employee"].id,
            assignee_id=users["agent"].id if assigned else None,
            status=status,
            priority=priority,
            response_due_at=created_at + timedelta(hours=target["first_response_hours"]),
            resolution_due_at=created_at + timedelta(hours=target["resolution_hours"]),
            first_response_at=(
                created_at + timedelta(hours=response_hours)
                if response_hours is not None else None
            ),
            resolved_at=(
                created_at + timedelta(hours=resolution_hours)
                if resolution_hours is not None else None
            ),
            created_at=created_at,
            updated_at=now,
        ))
        created["tickets"] += 1
    session.flush()
    return created


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("Run this command in a terminal to enter the demo password safely")
    print("Local demo only. Existing demo records and passwords will not be changed.")
    password = getpass("Choose one password for the three demo accounts: ")
    confirmation = getpass("Confirm demo password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match; nothing was added")
    with session_scope() as session:
        counts = seed_demo(session, password)
    print("Demo seed complete: " + ", ".join(f"{k} +{v}" for k, v in counts.items()))
    print("Accounts: demo.employee@example.test, demo.agent@example.test, demo.admin@example.test")


if __name__ == "__main__":
    main()
