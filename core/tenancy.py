"""Which organisation a request acts on, and what the user may do there.

Every tenant query goes through `current_membership()`, which only ever returns a membership the
signed-in user really has. Views then filter by `membership.organization`, so one tenant's data
cannot be reached from another's session, whatever IDs are sent.
"""
from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from .models import Membership, Role

SESSION_KEY = "org_id"


def current_membership(request) -> Membership:
    user = request.user
    if not user or not user.is_authenticated:
        raise NotAuthenticated()
    memberships = Membership.objects.select_related("organization").filter(user=user)
    wanted = request.session.get(SESSION_KEY)
    membership = memberships.filter(organization_id=wanted).first() if wanted else None
    if membership is None:
        membership = memberships.order_by("joined_at").first()
        if membership is None:
            raise PermissionDenied("You are not a member of any organisation yet.")
        request.session[SESSION_KEY] = membership.organization_id
    return membership


def require_role(membership: Membership, role: str) -> None:
    if not membership.at_least(role):
        label = {Role.ADMIN: "an admin or owner", Role.OWNER: "an owner"}[role]
        raise PermissionDenied(f"Only {label} can do this.")


def switch(request, organization_id: int) -> Membership:
    membership = Membership.objects.select_related("organization").filter(user=request.user, organization_id=organization_id).first()
    if membership is None:
        raise PermissionDenied("You are not a member of that organisation.")
    request.session[SESSION_KEY] = membership.organization_id
    return membership
