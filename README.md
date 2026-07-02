# CivicFix — Smart Civic Issue Reporting & SLA Resolution Tracker

Municipal complaint systems let reports vanish with no accountability. CivicFix
fixes that: every report gets a **priority score**, an **SLA deadline**, and
**automatically escalates** to the next authority tier if that deadline is missed —
with a full public audit trail.

## Not tied to any one country

The demo screenshots use sample data, but nothing in the code is hardcoded to
a specific country. Everything region-specific is a `.env` setting:

| What | Setting | Default |
|---|---|---|
| Timezone | `DJANGO_TIME_ZONE` | `UTC` |
| Escalation tier names | `TIER_1_NAME`, `TIER_2_NAME`, `TIER_3_NAME` | Local / Regional / Top Authority |
| Default map center | `DEFAULT_MAP_LAT`, `DEFAULT_MAP_LNG`, `DEFAULT_MAP_ZOOM` | neutral world view |

The 3-tier escalation pattern (local → regional → top authority) mirrors how
most municipal systems are structured, whatever they're actually called
locally — set the tier names to match your city/country in `.env`, e.g.:

```env
# India
TIER_1_NAME=Ward Officer
TIER_2_NAME=District Head
TIER_3_NAME=Municipal Commissioner

# USA
TIER_1_NAME=Ward Council
TIER_2_NAME=City Council
TIER_3_NAME=Mayor's Office
```

## Why this isn't a toy CRUD app

- **Priority scoring algorithm** — ranks open issues by severity weight, upvotes,
  and time-decay (not just newest-first). See `Issue.priority_score` in `issues/models.py`.
- **Automatic SLA escalation** — a management command (`escalate_issues`) scans for
  overdue issues and bumps them to the next tier, logging every escalation.
- **Geospatial duplicate detection** — new reports within 100m of an existing open
  issue of the same category are merged instead of creating clutter (haversine
  distance, no external geo library needed).
- **Transparency dashboard** — Chart.js analytics of resolution rate by category
  and escalation tier.

## Stack

| Layer | Tech |
|---|---|
| Backend | Django 5, Django REST Framework |
| Frontend | HTML / CSS / vanilla JS, Leaflet.js (map), Chart.js (analytics) |
| Database | Oracle SQL (production) / SQLite (local dev, zero setup) |
| Auth | Django's built-in auth — signup, login, logout, session-based |
| API | Full REST API under `/api/issues/` (DRF), token + session auth |
| DevOps | Docker, Docker Compose, GitHub Actions CI, Ansible deploy playbook |
| Hosting target | AWS EC2 |

## Running locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # defaults to SQLite, works immediately

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data # optional: adds demo issues to look at
python manage.py runserver
```

Migrations are already committed (`issues/migrations/0001_initial.py`), so
`migrate` works immediately — no `makemigrations` step needed unless you
change a model.

Visit `http://127.0.0.1:8000/`. Sign up for an account, or log in as
`demo_citizen` / `demopass123` if you ran the seed command.

To manually trigger the escalation engine (normally run on a schedule):

```bash
python manage.py escalate_issues
```

## Running with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts the web app **and** a background `escalator` service that runs
the SLA check every 30 minutes — demonstrating a real scheduled job, not just
a one-off script.

## Switching to Oracle

1. `pip install oracledb`
2. In `.env`, set `DB_ENGINE=oracle` and fill in `ORACLE_DSN`, `ORACLE_USER`,
   `ORACLE_PASSWORD`.
3. `python manage.py migrate`

No other code changes needed — `civicfix/settings.py` reads `DB_ENGINE` and
switches the `DATABASES` config automatically.

## REST API

| Endpoint | Method | Description |
|---|---|---|
| `/api/issues/` | GET, POST | List / create issues |
| `/api/issues/{id}/` | GET, PATCH, DELETE | Retrieve / update / delete (owner only) |
| `/api/issues/nearby/?lat=&lng=&radius=` | GET | Issues within radius (meters) |
| `/api/issues/{id}/upvote/` | POST | Toggle upvote |
| `/api/issues/{id}/resolve/` | POST | Mark resolved (owner/staff only) |

## Tests

```bash
python manage.py test
```

Covers the haversine distance function, priority scoring, duplicate
detection, and the escalation state machine. These same tests run in CI
on every push (`.github/workflows/ci.yml`).

## Deployment

`ansible/deploy.yml` provisions Docker on a fresh Ubuntu server, clones the
repo, and brings the stack up with `docker compose`. Point it at an EC2
instance:

```bash
ansible-playbook -i ansible/inventory.ini.example ansible/deploy.yml
```

**Before deploying publicly**, set these in `.env` (the app will refuse to
start with `DEBUG=0` and the default secret key, on purpose):

```env
DJANGO_SECRET_KEY=<generate one — see below>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your-domain.com,your-server-ip
CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

Generate a real secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

With `DEBUG=0`, HTTPS redirect, secure cookies, and HSTS turn on
automatically (see `civicfix/settings.py`). Put this behind Nginx or Caddy
for TLS termination, and swap `DB_ENGINE` to `oracle` (or Postgres) for a
real production database — SQLite is fine for the demo but not for
concurrent production traffic. In production, serve `MEDIA_URL` (uploaded
photos) via your reverse proxy or object storage rather than Django itself.

## Project structure

```
civicfix/
├── civicfix/          # Django project settings, urls
├── issues/            # Main app: models, views, API, templates, static, tests
│   ├── management/commands/escalate_issues.py   # SLA escalation engine
│   ├── management/commands/seed_demo_data.py
│   ├── templates/issues/
│   └── static/issues/{css,js}/
├── templates/registration/   # login.html, signup.html
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml
└── ansible/deploy.yml
```
