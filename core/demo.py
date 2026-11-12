"""The 'Try the demo' account: a throwaway user and organisation with realistic data, deleted after a day."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, Invitation, Membership, Organization, Plan, Project, Role, User, audit

TEAMMATES = [("Lena Fischer", Role.ADMIN), ("Tom Berger", Role.MEMBER), ("Mia Novak", Role.MEMBER)]
PROJECTS = [
    ("Customer portal redesign", Project.Status.ACTIVE),
    ("Spring product launch", Project.Status.PLANNED),
    ("Warehouse barcode scanning", Project.Status.ACTIVE),
    ("Migrate invoices to the new ERP", Project.Status.DONE),
]


def purge_expired() -> int:
    cutoff = timezone.now() - timedelta(hours=settings.TEAMBASE["DEMO_RETENTION_HOURS"])
    old_users = User.objects.filter(is_demo=True, date_joined__lt=cutoff)
    orgs = Organization.objects.filter(memberships__user__in=old_users).distinct()
    count = orgs.count()
    orgs.delete()
    old_users.delete()
    return count


@transaction.atomic
def create_demo_account() -> User:
    tag = secrets.token_hex(4)
    user = User.objects.create_user(f"demo-{tag}@demo.invalid", password=None, name="Alex Demo", is_demo=True)
    org = Organization.objects.create(name="Acme Outdoor (demo)", plan=Plan.PRO)  # 4 people + 1 invite exceed Free
    Membership.objects.create(user=user, organization=org, role=Role.OWNER)
    audit(org, user, "organisation.created", org.name)
    for name, role in TEAMMATES:
        first = name.split()[0].lower()
        mate = User.objects.create_user(f"{first}-{tag}@demo.invalid", password=None, name=name, is_demo=True)
        Membership.objects.create(user=mate, organization=org, role=role)
        audit(org, user, "member.added", f"{name} as {role}")
    for name, status in PROJECTS:
        Project.objects.create(organization=org, name=name, status=status, created_by=user)
        audit(org, user, "project.created", name)
    Invitation.objects.create(organization=org, email=f"sam-{tag}@demo.invalid", role=Role.MEMBER, invited_by=user)
    audit(org, user, "invitation.sent", "Sam (member)")
    # Spread the activity log over the last few days so it reads naturally.
    for index, event in enumerate(AuditEvent.objects.filter(organization=org).order_by("id")):
        AuditEvent.objects.filter(pk=event.pk).update(created_at=timezone.now() - timedelta(hours=2 * (12 - index)))
    return user
