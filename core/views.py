"""The JSON API used by the Next.js frontend. Session cookies plus CSRF, one origin, no tokens in the browser."""
from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError as ApiError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import billing, demo, limits, tenancy
from .models import PLAN_LIMITS, AuditEvent, Invitation, Membership, Organization, Project, Role, User, audit

log = logging.getLogger(__name__)


def _text(data, key: str, limit: int = 120, required: bool = True) -> str:
    value = str(data.get(key, "")).strip()[:limit]
    if required and not value:
        raise ApiError({key: "This field is required."})
    return value


def _me(request) -> dict:
    user = request.user
    membership = tenancy.current_membership(request)
    org = membership.organization
    return {
        "user": {"id": user.pk, "name": user.name, "email": user.email, "is_demo": user.is_demo},
        "organization": {"id": org.pk, "name": org.name, "plan": org.plan, "role": membership.role},
        "organizations": [
            {"id": m.organization_id, "name": m.organization.name, "role": m.role}
            for m in Membership.objects.select_related("organization").filter(user=user)
        ],
    }


def _member(m: Membership) -> dict:
    return {"id": m.pk, "user_id": m.user_id, "name": m.user.name, "email": m.user.email, "role": m.role, "joined_at": m.joined_at}


def _invite(i: Invitation, include_link: bool) -> dict:
    data = {"id": i.pk, "email": i.email, "role": i.role, "expires_at": i.expires_at, "is_open": i.is_open}
    if include_link:
        data["link"] = i.link()  # shown to admins so they can share it; this demo sends no email
    return data


def _project(p: Project) -> dict:
    return {"id": p.pk, "name": p.name, "status": p.status, "created_by": p.created_by.name if p.created_by else None, "updated_at": p.updated_at}


def _usage(org: Organization) -> dict:
    return {"seats_used": org.seats_used(), "seats": org.limits["seats"], "projects_used": org.projects.count(), "projects": org.limits["projects"]}


def _require_csrf(request) -> None:
    """DRF only checks CSRF for signed-in users, and Django's csrf_protect has no effect on DRF views,
    so the anonymous endpoints (sign-up, login, demo) run the same check explicitly."""
    SessionAuthentication().enforce_csrf(request)


# ---- auth --------------------------------------------------------------------------------
@ensure_csrf_cookie
def csrf(request):
    """The frontend calls this once so the CSRF cookie exists before the first POST."""
    return JsonResponse({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    _require_csrf(request)
    if not limits.allow("signup", limits.client_ip(request), settings.TEAMBASE["SIGNUPS_PER_IP_PER_DAY"]):
        raise PermissionDenied("Too many sign-ups from this network today. Try again tomorrow.")
    data = request.data
    name, email, password = _text(data, "name"), _text(data, "email", 254).lower(), str(data.get("password", ""))
    token = str(data.get("invite_token", "")).strip()
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError({"email": "Enter a valid email address."})
    invitation = Invitation.objects.select_related("organization").filter(token=token).first() if token else None
    if token and (invitation is None or not invitation.is_open or invitation.email.lower() != email):
        raise ApiError({"invite_token": "This invitation is not valid for that email address."})
    org_name = "" if invitation else _text(data, "organization")
    candidate = User(email=email, name=name)
    try:
        password_validation.validate_password(password, candidate)
    except ValidationError as exc:
        raise ApiError({"password": list(exc.messages)})
    try:
        with transaction.atomic():
            user = User.objects.create_user(email, password, name=name)
            if invitation:
                org = invitation.organization
                Membership.objects.create(user=user, organization=org, role=invitation.role)
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=["accepted_at"])
                audit(org, user, "invitation.accepted", f"{email} joined as {invitation.role}")
            else:
                org = Organization.objects.create(name=org_name)
                Membership.objects.create(user=user, organization=org, role=Role.OWNER)
                audit(org, user, "organisation.created", org.name)
    except IntegrityError:
        raise ApiError({"email": "An account with this email already exists. Log in instead."})
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session[tenancy.SESSION_KEY] = org.pk
    return Response(_me(request), status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    _require_csrf(request)
    if not limits.allow("login", limits.client_ip(request), settings.TEAMBASE["LOGIN_ATTEMPTS_PER_IP_PER_HOUR"]):
        raise PermissionDenied("Too many sign-in attempts. Wait a while and try again.")
    user = authenticate(request, username=_text(request.data, "email", 254).lower(), password=str(request.data.get("password", "")))
    if user is None:
        raise ApiError({"detail": "Email or password is incorrect."})
    login(request, user)
    return Response(_me(request))


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def demo_login(request):
    _require_csrf(request)
    if not settings.TEAMBASE["DEMO_ENABLED"]:
        raise PermissionDenied("The demo is switched off on this installation.")
    if not limits.allow("demo", limits.client_ip(request), settings.TEAMBASE["SIGNUPS_PER_IP_PER_DAY"]):
        raise PermissionDenied("Too many demo accounts from this network today. Try again tomorrow.")
    demo.purge_expired()
    user = demo.create_demo_account()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response(_me(request), status=201)


@api_view(["GET"])
def me(request):
    return Response(_me(request))


# ---- organisations -----------------------------------------------------------------------
@api_view(["POST"])
def create_org(request):
    org = Organization.objects.create(name=_text(request.data, "name"))
    Membership.objects.create(user=request.user, organization=org, role=Role.OWNER)
    audit(org, request.user, "organisation.created", org.name)
    request.session[tenancy.SESSION_KEY] = org.pk
    return Response(_me(request), status=201)


@api_view(["POST"])
def switch_org(request, org_id: int):
    tenancy.switch(request, org_id)
    return Response(_me(request))


@api_view(["PATCH"])
def update_org(request):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.ADMIN)
    org = membership.organization
    old = org.name
    org.name = _text(request.data, "name")
    org.save(update_fields=["name"])
    audit(org, request.user, "organisation.renamed", f"{old} to {org.name}")
    return Response(_me(request))


@api_view(["POST"])
def leave_org(request):
    membership = tenancy.current_membership(request)
    org = membership.organization
    if membership.role == Role.OWNER and not org.memberships.filter(role=Role.OWNER).exclude(pk=membership.pk).exists():
        raise ApiError({"detail": "You are the only owner. Make someone else an owner before leaving."})
    if Membership.objects.filter(user=request.user).count() == 1:
        raise ApiError({"detail": "This is your only organisation. Create another one before leaving."})
    membership.delete()
    audit(org, request.user, "member.left", request.user.email)
    request.session.pop(tenancy.SESSION_KEY, None)
    return Response(_me(request))


# ---- members and invitations -------------------------------------------------------------
@api_view(["GET"])
def members(request):
    membership = tenancy.current_membership(request)
    org = membership.organization
    admin = membership.at_least(Role.ADMIN)
    return Response({
        "members": [_member(m) for m in org.memberships.select_related("user")],
        "invitations": [_invite(i, admin) for i in org.invitations.filter(accepted_at__isnull=True)] if admin else [],
        "usage": _usage(org),
        "can_manage": admin,
        "can_change_roles": membership.role == Role.OWNER,
    })


@api_view(["PATCH", "DELETE"])
def member_detail(request, member_id: int):
    membership = tenancy.current_membership(request)
    org = membership.organization
    target = org.memberships.select_related("user").filter(pk=member_id).first()
    if target is None:
        raise ApiError({"detail": "That member was not found."})
    owners = org.memberships.filter(role=Role.OWNER)
    if request.method == "PATCH":
        tenancy.require_role(membership, Role.OWNER)
        role = str(request.data.get("role", ""))
        if role not in Role.values:
            raise ApiError({"role": "Choose owner, admin or member."})
        if target.role == Role.OWNER and role != Role.OWNER and owners.count() == 1:
            raise ApiError({"detail": "An organisation needs at least one owner."})
        target.role = role
        target.save(update_fields=["role"])
        audit(org, request.user, "member.role_changed", f"{target.user.email} is now {role}")
        return Response(_member(target))
    # Admins may remove members; only owners may remove admins or owners.
    tenancy.require_role(membership, Role.ADMIN)
    if target.at_least(Role.ADMIN):
        tenancy.require_role(membership, Role.OWNER)
    if target.role == Role.OWNER and owners.count() == 1:
        raise ApiError({"detail": "An organisation needs at least one owner."})
    if target.pk == membership.pk:
        raise ApiError({"detail": "Use 'Leave organisation' to remove yourself."})
    target.delete()
    audit(org, request.user, "member.removed", target.user.email)
    return Response(status=204)


@api_view(["POST"])
def invite(request):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.ADMIN)
    org = membership.organization
    email = _text(request.data, "email", 254).lower()
    role = str(request.data.get("role", Role.MEMBER))
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError({"email": "Enter a valid email address."})
    if role not in (Role.ADMIN, Role.MEMBER):
        raise ApiError({"role": "Invite people as admin or member."})
    if role == Role.ADMIN:
        tenancy.require_role(membership, Role.OWNER)
    if org.memberships.filter(user__email__iexact=email).exists():
        raise ApiError({"email": "This person is already a member."})
    if org.invitations.filter(email__iexact=email, accepted_at__isnull=True, expires_at__gt=timezone.now()).exists():
        raise ApiError({"email": "This person already has an open invitation."})
    if org.seats_used() >= org.limits["seats"]:
        raise ApiError({"detail": f"Your {org.get_plan_display()} plan has {org.limits['seats']} seats and they are all used. Upgrade to invite more people."})
    invitation = Invitation.objects.create(organization=org, email=email, role=role, invited_by=request.user)
    audit(org, request.user, "invitation.sent", f"{email} as {role}")
    return Response(_invite(invitation, True), status=201)


@api_view(["DELETE"])
def revoke_invite(request, invite_id: int):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.ADMIN)
    invitation = membership.organization.invitations.filter(pk=invite_id, accepted_at__isnull=True).first()
    if invitation is None:
        raise ApiError({"detail": "That invitation was not found."})
    invitation.delete()
    audit(membership.organization, request.user, "invitation.revoked", invitation.email)
    return Response(status=204)


@api_view(["GET"])
@permission_classes([AllowAny])
def invitation_preview(request, token: str):
    invitation = Invitation.objects.select_related("organization", "invited_by").filter(token=token).first()
    if invitation is None or not invitation.is_open:
        return Response({"valid": False})
    return Response({
        "valid": True, "organization": invitation.organization.name, "email": invitation.email, "role": invitation.role,
        "invited_by": invitation.invited_by.name if invitation.invited_by else None,
        "signed_in_as": request.user.email if request.user and request.user.is_authenticated else None,
    })


@api_view(["POST"])
def accept_invitation(request, token: str):
    with transaction.atomic():
        invitation = Invitation.objects.select_for_update().select_related("organization").filter(token=token).first()
        if invitation is None or not invitation.is_open:
            raise ApiError({"detail": "This invitation has expired or was already used."})
        if invitation.email.lower() != request.user.email.lower():
            raise PermissionDenied(f"This invitation is for {invitation.email}. Sign in with that address to accept it.")
        org = invitation.organization
        Membership.objects.get_or_create(user=request.user, organization=org, defaults={"role": invitation.role})
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
        audit(org, request.user, "invitation.accepted", f"{request.user.email} joined as {invitation.role}")
    request.session[tenancy.SESSION_KEY] = org.pk
    return Response(_me(request))


# ---- the example tenant resource ---------------------------------------------------------
@api_view(["GET", "POST"])
def projects(request):
    membership = tenancy.current_membership(request)
    org = membership.organization
    if request.method == "GET":
        return Response({"projects": [_project(p) for p in org.projects.select_related("created_by")], "usage": _usage(org)})
    if org.projects.count() >= org.limits["projects"]:
        raise ApiError({"detail": f"Your {org.get_plan_display()} plan allows {org.limits['projects']} projects. Upgrade to add more."})
    status = str(request.data.get("status", Project.Status.PLANNED))
    if status not in Project.Status.values:
        raise ApiError({"status": "Choose planned, active or done."})
    project = Project.objects.create(organization=org, name=_text(request.data, "name"), status=status, created_by=request.user)
    audit(org, request.user, "project.created", project.name)
    return Response(_project(project), status=201)


@api_view(["PATCH", "DELETE"])
def project_detail(request, project_id: int):
    membership = tenancy.current_membership(request)
    org = membership.organization
    project = org.projects.filter(pk=project_id).first()  # scoped to the tenant: other orgs' IDs simply 404
    if project is None:
        raise ApiError({"detail": "That project was not found."})
    if request.method == "DELETE":
        if project.created_by_id != request.user.pk:
            tenancy.require_role(membership, Role.ADMIN)
        project.delete()
        audit(org, request.user, "project.deleted", project.name)
        return Response(status=204)
    if "name" in request.data:
        project.name = _text(request.data, "name")
    if "status" in request.data:
        if request.data["status"] not in Project.Status.values:
            raise ApiError({"status": "Choose planned, active or done."})
        project.status = request.data["status"]
    project.save()
    audit(org, request.user, "project.updated", f"{project.name} ({project.status})")
    return Response(_project(project))


# ---- billing and activity ----------------------------------------------------------------
@api_view(["GET"])
def billing_overview(request):
    membership = tenancy.current_membership(request)
    org = membership.organization
    return Response({
        "plan": org.plan, "plans": billing.plans(), "usage": _usage(org),
        "mode": "stripe" if billing.stripe_enabled() else "demo",
        "can_manage": membership.role == Role.OWNER,
        "has_subscription": bool(org.stripe_subscription_id),
    })


@api_view(["POST"])
def change_plan(request):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.OWNER)
    org = membership.organization
    old = org.plan
    try:
        result = billing.start_checkout(org, str(request.data.get("plan", "")), request.user.email)
    except billing.BillingError as exc:
        raise ApiError({"detail": str(exc)})
    if result.get("changed"):
        audit(org, request.user, "plan.changed", f"{old} to {org.plan} (demo billing, no payment taken)")
    return Response(result)


@api_view(["POST"])
def billing_portal(request):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.OWNER)
    try:
        return Response(billing.portal(membership.organization))
    except billing.BillingError as exc:
        raise ApiError({"detail": str(exc)})


@csrf_exempt
def stripe_webhook(request):
    """Stripe calls this; the signature proves the event is genuine, so no session or CSRF is involved."""
    if request.method != "POST" or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=404)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""), settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)
    log.info("Stripe webhook: %s", billing.handle_event(event))
    return HttpResponse(status=200)


@api_view(["GET"])
def activity(request):
    membership = tenancy.current_membership(request)
    tenancy.require_role(membership, Role.ADMIN)
    events = AuditEvent.objects.filter(organization=membership.organization).select_related("actor")[:100]
    return Response({"events": [
        {"id": e.pk, "action": e.action, "detail": e.detail, "actor": e.actor.name if e.actor else "Someone", "at": e.created_at}
        for e in events
    ]})


def healthz(request):
    return JsonResponse({"ok": True, "billing": "stripe" if billing.stripe_enabled() else "demo", "plans": list(PLAN_LIMITS)})
