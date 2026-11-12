"""Users, organisations (tenants), roles, invitations, plans, an example tenant resource and an audit log."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Signs in with an email address. Belongs to one or more organisations through memberships."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False, help_text="Created by the 'Try the demo' button; deleted after a day.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self) -> str:
        return self.email


class Plan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"
    BUSINESS = "business", "Business"


# Plan limits live in code so they are versioned and testable. Prices are for display; Stripe holds the real ones.
PLAN_LIMITS = {
    Plan.FREE: {"seats": 3, "projects": 5, "price": "0"},
    Plan.PRO: {"seats": 10, "projects": 50, "price": "29"},
    Plan.BUSINESS: {"seats": 50, "projects": 500, "price": "99"},
}


class Organization(models.Model):
    """A tenant. Every piece of customer data hangs off one of these."""

    name = models.CharField(max_length=120)
    plan = models.CharField(max_length=12, choices=Plan.choices, default=Plan.FREE)
    stripe_customer_id = models.CharField(max_length=80, blank=True)
    stripe_subscription_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    @property
    def limits(self) -> dict:
        return PLAN_LIMITS[self.plan]

    def seats_used(self) -> int:
        pending = self.invitations.filter(accepted_at__isnull=True, expires_at__gt=timezone.now()).count()
        return self.memberships.count() + pending


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


ROLE_RANK = {Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "organization"], name="one_membership_per_org")]
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.user} in {self.organization} ({self.role})"

    def at_least(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


def _token() -> str:
    return secrets.token_urlsafe(24)


def _expiry():
    return timezone.now() + timedelta(days=7)


class Invitation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=[(Role.ADMIN, "Admin"), (Role.MEMBER, "Member")], default=Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=_token)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_open(self) -> bool:
        return self.accepted_at is None and self.expires_at > timezone.now()

    def link(self) -> str:
        return f"{settings.SITE_URL}/invite/?token={self.token}"


class Project(models.Model):
    """The example tenant resource. Replace it with your product's own data."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        DONE = "done", "Done"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class AuditEvent(models.Model):
    """Who did what, in which organisation. Shown to admins under Activity."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


def audit(org: Organization, actor, action: str, detail: str = "") -> None:
    AuditEvent.objects.create(organization=org, actor=actor, action=action, detail=detail[:300])
