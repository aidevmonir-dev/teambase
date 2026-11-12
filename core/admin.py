from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditEvent, Invitation, Membership, Organization, Project, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "is_demo", "is_staff", "date_joined"]
    list_filter = ["is_demo", "is_staff"]
    search_fields = ["email", "name"]
    fieldsets = [
        (None, {"fields": ["email", "name", "password"]}),
        ("Status", {"fields": ["is_active", "is_demo", "is_staff", "is_superuser"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"], "fields": ["email", "name", "password1", "password2"]})]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "plan", "created_at"]
    list_filter = ["plan"]
    search_fields = ["name"]
    inlines = [MembershipInline]


admin.site.register(Invitation)
admin.site.register(Project)
admin.site.register(AuditEvent)
