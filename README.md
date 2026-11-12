# TeamBase

The part every SaaS needs, built once and tested: sign-up, organisations, roles, invitations, plans
with limits, Stripe billing and an audit log. Django REST backend, Next.js frontend, one deployment.

Built by [Devomio](https://devomio.com/) as an open starting point for multi-tenant products.

## What is included

- **Organisations as tenants.** Every record belongs to an organisation, and every API query is
  scoped to the signed-in member's organisation (`core/tenancy.py`). Users can belong to several
  organisations and switch between them.
- **Roles enforced on the server.** Owners manage billing and roles; admins invite and remove
  members; members work on the product. The last owner cannot be demoted or removed.
- **Invitations with seat limits.** Invite by email with a one-time link that expires after seven
  days. Open invitations count as seats, so a team cannot exceed its plan.
- **Plans and Stripe billing.** Free, Pro and Business with seat and project limits. Upgrades go
  through Stripe Checkout; the plan only changes when Stripe's signed webhook confirms payment.
  Owners manage invoices in the Stripe customer portal. Without Stripe keys the app runs in demo
  billing mode.
- **Audit log.** Invitations, role changes, plan changes and project changes, visible to admins.
- **An example feature.** "Projects" shows how tenant data, plan limits and permissions fit
  together. Replace it with your product.
- **A demo account.** "Try the demo" signs a visitor into a sample company with a team, projects and
  activity, deleted after 24 hours.

## Architecture

```
Browser ──► Django (one origin)
             ├── /api/...    Django REST Framework: session auth + CSRF
             ├── /admin/     Django admin
             └── everything else: the Next.js app, exported as static files
```

- **Backend** (`core/`): Django 5.2, Django REST Framework, Stripe. Session cookies and CSRF, so no
  tokens are stored in the browser.
- **Frontend** (`frontend/`): Next.js 16 (App Router), TypeScript, Tailwind CSS 4. Built with
  `output: "export"` into static files, so it can be served by Django, a CDN or any web server.
- **One origin** means no CORS configuration and plain, `HttpOnly` session cookies.

| File | Role |
|---|---|
| `core/models.py` | Users, organisations, memberships, invitations, plans, projects, audit events |
| `core/tenancy.py` | Resolves the current organisation and checks roles for every request |
| `core/views.py` | The REST API |
| `core/billing.py` | Plan limits, Stripe Checkout, the customer portal and webhook handling |
| `frontend/lib/api.ts` | API client with CSRF handling and readable errors |
| `frontend/app/app/` | The signed-in area: projects, team, billing, activity, settings |

## Run it locally

Requires Python 3.12+ and Node 22+.

```bash
git clone https://github.com/aidevmonir-dev/teambase.git
cd teambase
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
cp .env.example .env                               # set DEBUG=1
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver               # API on http://127.0.0.1:8000

cd frontend
npm install
npm run dev                                        # app on http://localhost:3000, /api proxied to Django
```

To serve everything from Django on one port, run `npm run build` in `frontend/` and open
http://127.0.0.1:8000/.

### With Docker

```bash
cp .env.example .env      # set SECRET_KEY and ALLOWED_HOSTS=localhost
docker compose up --build
```

The image builds the frontend in a Node stage and serves it from Django.

## Stripe

1. Create two recurring prices in Stripe (Pro and Business) and set `STRIPE_PRICE_PRO` and
   `STRIPE_PRICE_BUSINESS`.
2. Set `STRIPE_SECRET_KEY`.
3. Add a webhook endpoint for `https://YOUR-SITE/api/billing/webhook/` with the events
   `checkout.session.completed`, `customer.subscription.updated` and
   `customer.subscription.deleted`, and set `STRIPE_WEBHOOK_SECRET`.

The plan is changed only by verified webhook events, never by the browser returning from Checkout.

## Deploying to shared hosting without Node

CI (`.github/workflows/ci.yml`) runs the tests, builds the frontend and publishes the static files
to the `frontend-dist` branch. On the server, `deploy/cpanel_setup.py` migrates the database,
downloads that build into `FRONTEND_DIR` and restarts the app. This is how the live demo runs on a
cPanel host.

## Tests

```bash
DEBUG=1 python manage.py test
```

The suite covers tenant isolation (another organisation's IDs cannot be read or changed), every
role rule, CSRF on every write including sign-up and login, invitations, seat and project limits,
demo billing, Stripe Checkout parameters and webhook verification, multiple organisations and demo
expiry. Stripe calls are mocked, so the tests run offline.

## Need a SaaS product built?

Devomio builds production SaaS on a base like this: your product features, your billing model,
single sign-on, email, analytics and hosting in the EU. See [devomio.com](https://devomio.com/) or
write to hello@devomio.com.

## Licence

MIT. See [LICENSE](LICENSE).
