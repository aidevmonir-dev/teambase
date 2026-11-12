import json
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core import billing, demo
from core.models import AuditEvent, Invitation, Membership, Organization, Plan, Project, Role, User

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD = "correct horse battery 7"


class Api:
    """A browser-like client: keeps the session, sends the CSRF header like the frontend does."""

    def __init__(self):
        self.c = Client(enforce_csrf_checks=True)
        self.c.get("/api/auth/csrf/")

    def _h(self):
        return {"HTTP_X_CSRFTOKEN": self.c.cookies["csrftoken"].value}

    def get(self, url):
        return self.c.get(url)

    def post(self, url, data=None):
        return self.c.post(url, json.dumps(data or {}), content_type="application/json", **self._h())

    def patch(self, url, data):
        return self.c.patch(url, json.dumps(data), content_type="application/json", **self._h())

    def delete(self, url):
        return self.c.delete(url, **self._h())

    def signup(self, email, org="Acme", name="Ana", **extra):
        return self.post("/api/auth/signup/", {"name": name, "email": email, "password": PASSWORD, "organization": org, **extra})


@override_settings(CACHES=LOCMEM, STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
class TenantTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = Api()
        self.assertEqual(self.owner.signup("owner@acme.test").status_code, 201)
        self.org = Organization.objects.get(name="Acme")

    def test_signup_creates_owner_and_login_works(self):
        me = self.owner.get("/api/auth/me/").json()
        self.assertEqual(me["organization"]["role"], "owner")
        self.assertEqual(me["organization"]["plan"], "free")
        other = Api()
        self.assertEqual(other.post("/api/auth/login/", {"email": "OWNER@acme.test", "password": "wrong"}).status_code, 400)
        self.assertEqual(other.post("/api/auth/login/", {"email": "OWNER@acme.test", "password": PASSWORD}).status_code, 200)

    def test_signup_validation(self):
        api = Api()
        self.assertEqual(api.signup("owner@acme.test").status_code, 400)  # duplicate
        weak = api.post("/api/auth/signup/", {"name": "B", "email": "b@x.test", "password": "password", "organization": "B"})
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.json())

    def test_csrf_is_required(self):
        raw = Client(enforce_csrf_checks=True)
        raw.force_login(User.objects.get(email="owner@acme.test"))
        self.assertEqual(raw.post("/api/org/projects/", {"name": "x"}).status_code, 403)
        self.assertEqual(Client(enforce_csrf_checks=True).post("/api/auth/login/", {"email": "a", "password": "b"}).status_code, 403)

    def test_tenants_cannot_see_each_other(self):
        project = self.owner.post("/api/org/projects/", {"name": "Secret plan"}).json()
        intruder = Api()
        intruder.signup("eve@evil.test", org="Evil Corp", name="Eve")
        self.assertEqual(intruder.get("/api/org/projects/").json()["projects"], [])
        self.assertEqual(intruder.patch(f"/api/org/projects/{project['id']}/", {"name": "pwned"}).status_code, 400)
        self.assertEqual(intruder.delete(f"/api/org/projects/{project['id']}/").status_code, 400)
        self.assertEqual(intruder.post(f"/api/orgs/{self.org.pk}/switch/").status_code, 403)
        self.assertEqual(Project.objects.get().name, "Secret plan")

    def test_unauthenticated_requests_are_refused(self):
        anon = Api()
        for url in ["/api/auth/me/", "/api/org/projects/", "/api/org/members/", "/api/org/billing/"]:
            self.assertEqual(anon.get(url).status_code, 403, url)

    def invite_and_join(self, email, role="member"):
        invite = self.owner.post("/api/org/invitations/", {"email": email, "role": role})
        self.assertEqual(invite.status_code, 201, invite.content)
        token = invite.json()["link"].split("token=")[1]
        api = Api()
        self.assertTrue(api.get(f"/api/invitations/{token}/").json()["valid"])
        joined = api.signup(email, name=email.split("@")[0], invite_token=token)
        self.assertEqual(joined.status_code, 201, joined.content)
        return api

    def test_invitation_flow_and_roles(self):
        member = self.invite_and_join("mia@acme.test")
        me = member.get("/api/auth/me/").json()
        self.assertEqual((me["organization"]["name"], me["organization"]["role"]), ("Acme", "member"))
        self.assertEqual(Organization.objects.count(), 1)  # joining did not create a second org

        # Members can work on projects but not manage the team, billing or activity.
        self.assertEqual(member.post("/api/org/projects/", {"name": "Mine"}).status_code, 201)
        self.assertEqual(member.post("/api/org/invitations/", {"email": "x@acme.test"}).status_code, 403)
        self.assertEqual(member.post("/api/org/billing/change/", {"plan": "pro"}).status_code, 403)
        self.assertEqual(member.get("/api/org/activity/").status_code, 403)
        self.assertEqual(member.get("/api/org/members/").json()["invitations"], [])

        # Only owners change roles, and the last owner cannot be demoted.
        owner_membership = Membership.objects.get(user__email="owner@acme.test")
        self.assertEqual(self.owner.patch(f"/api/org/members/{owner_membership.pk}/", {"role": "member"}).status_code, 400)
        mia = Membership.objects.get(user__email="mia@acme.test")
        self.assertEqual(member.patch(f"/api/org/members/{mia.pk}/", {"role": "owner"}).status_code, 403)
        self.assertEqual(self.owner.patch(f"/api/org/members/{mia.pk}/", {"role": "admin"}).json()["role"], "admin")

    def test_invitation_must_match_email(self):
        invite = self.owner.post("/api/org/invitations/", {"email": "tom@acme.test"}).json()
        token = invite["link"].split("token=")[1]
        stranger = Api()
        stranger.signup("someone@else.test", org="Else")
        self.assertEqual(stranger.post(f"/api/invitations/{token}/accept/").status_code, 403)
        self.assertEqual(Api().signup("other@else.test", invite_token=token).status_code, 400)

    def test_seat_limit(self):
        self.invite_and_join("a@acme.test")
        self.owner.post("/api/org/invitations/", {"email": "b@acme.test"})  # 2 members + 1 invite = 3 seats (Free)
        blocked = self.owner.post("/api/org/invitations/", {"email": "c@acme.test"})
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("seats", blocked.json()["detail"])

    def test_project_limit_and_permissions(self):
        for i in range(5):
            self.assertEqual(self.owner.post("/api/org/projects/", {"name": f"P{i}"}).status_code, 201)
        self.assertEqual(self.owner.post("/api/org/projects/", {"name": "P6"}).status_code, 400)
        member = self.invite_and_join("m@acme.test")
        someone_elses = Project.objects.first()
        self.assertEqual(member.delete(f"/api/org/projects/{someone_elses.pk}/").status_code, 403)
        self.assertEqual(member.patch(f"/api/org/projects/{someone_elses.pk}/", {"status": "done"}).json()["status"], "done")

    def test_demo_billing_mode(self):
        overview = self.owner.get("/api/org/billing/").json()
        self.assertEqual((overview["mode"], overview["plan"]), ("demo", "free"))
        self.assertEqual(self.owner.post("/api/org/billing/change/", {"plan": "business"}).json()["changed"], True)
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan, "business")
        self.assertTrue(AuditEvent.objects.filter(action="plan.changed").exists())
        for i in range(6):
            Project.objects.create(organization=self.org, name=f"x{i}")
        refused = self.owner.post("/api/org/billing/change/", {"plan": "free"})  # 6 projects > Free's 5
        self.assertEqual(refused.status_code, 400)

    def test_multiple_organisations(self):
        created = self.owner.post("/api/orgs/", {"name": "Side Project"}).json()
        self.assertEqual(created["organization"]["name"], "Side Project")
        self.assertEqual(len(created["organizations"]), 2)
        back = self.owner.post(f"/api/orgs/{self.org.pk}/switch/").json()
        self.assertEqual(back["organization"]["name"], "Acme")
        self.assertEqual(self.owner.post("/api/org/leave/").status_code, 400)  # only owner


@override_settings(CACHES=LOCMEM, STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
class DemoTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_demo_account(self):
        api = Api()
        me = api.post("/api/auth/demo/").json()
        self.assertTrue(me["user"]["is_demo"])
        self.assertEqual(me["organization"]["plan"], "pro")
        self.assertEqual(len(api.get("/api/org/projects/").json()["projects"]), 4)
        self.assertEqual(len(api.get("/api/org/members/").json()["members"]), 4)
        self.assertGreater(len(api.get("/api/org/activity/").json()["events"]), 5)

    def test_demo_accounts_expire(self):
        Api().post("/api/auth/demo/")
        User.objects.filter(is_demo=True).update(date_joined=timezone.now() - timedelta(days=2))
        demo.purge_expired()
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)

    def test_demo_cannot_sign_in_with_a_password(self):
        user = demo.create_demo_account()
        self.assertFalse(user.has_usable_password())


@override_settings(
    CACHES=LOCMEM, STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x",
    STRIPE_PRICES={"pro": "price_pro", "business": "price_biz"}, SITE_URL="https://app.example.com",
)
class StripeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = Api()
        self.api.signup("owner@acme.test")
        self.org = Organization.objects.get()

    def test_checkout_creates_a_session_and_does_not_change_the_plan(self):
        with mock.patch("stripe.checkout.Session.create", return_value=mock.Mock(url="https://checkout.stripe.test/s")) as create:
            result = self.api.post("/api/org/billing/change/", {"plan": "pro"}).json()
        self.assertEqual(result["url"], "https://checkout.stripe.test/s")
        params = create.call_args.kwargs
        self.assertEqual(params["line_items"][0]["price"], "price_pro")
        self.assertEqual(params["metadata"], {"organization_id": str(self.org.pk), "plan": "pro"})
        self.assertTrue(params["success_url"].startswith("https://app.example.com/app/billing/"))
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan, "free")  # only the webhook upgrades

    def webhook(self, event, valid=True):
        target = "stripe.Webhook.construct_event"
        effect = {"return_value": event} if valid else {"side_effect": __import__("stripe").SignatureVerificationError("bad", "sig")}
        with mock.patch(target, **effect):
            return Client().post("/api/billing/webhook/", "{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=x")

    def test_webhook_applies_verified_events_only(self):
        completed = {"type": "checkout.session.completed", "data": {"object": {
            "metadata": {"organization_id": str(self.org.pk), "plan": "pro"}, "customer": "cus_1", "subscription": "sub_1"}}}
        self.assertEqual(self.webhook(completed, valid=False).status_code, 400)
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan, "free")
        self.assertEqual(self.webhook(completed).status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual((self.org.plan, self.org.stripe_customer_id), ("pro", "cus_1"))
        deleted = {"type": "customer.subscription.deleted", "data": {"object": {"customer": "cus_1", "metadata": {}}}}
        self.webhook(deleted)
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan, "free")

    def test_plan_mapping(self):
        self.assertEqual(billing.plan_for_price("price_biz"), "business")
        self.assertIsNone(billing.plan_for_price("price_unknown"))
        self.assertEqual([p["id"] for p in billing.plans()], [Plan.FREE, Plan.PRO, Plan.BUSINESS])
        self.assertEqual(Invitation.objects.count(), 0)
        self.assertEqual(Role.OWNER, "owner")
