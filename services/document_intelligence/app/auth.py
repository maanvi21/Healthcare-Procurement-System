from typing import Callable
from fastapi import Header, HTTPException

VALID_ROLES = {
    "department_manager",
    "finance_manager",
    "compliance_officer",
    "procurement_director",
}


def require_roles(allowed_roles: list[str]) -> Callable:
    def dependency(
        x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> str:
        role = (x_user_role or "").strip().lower()
        if not role:
            role = "department_manager"

        if role not in VALID_ROLES or role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for role '{role}'. Required: {allowed_roles}",
            )
        return role

    return dependency


def get_current_role(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> str:
    role = (x_user_role or "").strip().lower()
    return role if role in VALID_ROLES else "department_manager"
