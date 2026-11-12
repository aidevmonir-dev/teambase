from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/signup/", views.signup),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/demo/", views.demo_login),
    path("auth/me/", views.me),
    path("orgs/", views.create_org),
    path("orgs/<int:org_id>/switch/", views.switch_org),
    path("org/", views.update_org),
    path("org/leave/", views.leave_org),
    path("org/members/", views.members),
    path("org/members/<int:member_id>/", views.member_detail),
    path("org/invitations/", views.invite),
    path("org/invitations/<int:invite_id>/", views.revoke_invite),
    path("invitations/<str:token>/", views.invitation_preview),
    path("invitations/<str:token>/accept/", views.accept_invitation),
    path("org/projects/", views.projects),
    path("org/projects/<int:project_id>/", views.project_detail),
    path("org/billing/", views.billing_overview),
    path("org/billing/change/", views.change_plan),
    path("org/billing/portal/", views.billing_portal),
    path("org/activity/", views.activity),
    path("billing/webhook/", views.stripe_webhook),
]
