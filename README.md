# CivicFix

CivicFix is a Django civic issue reporting and tracking platform. Residents can report neighborhood problems with a description, category, location, and photos; find and support existing reports; and follow status updates. Staff can assign departments, set priorities, and update progress.

## Features

- Registration, login/logout, user profile, email verification, and Django password recovery. Signup creates the account and redirects to login; users sign in manually.
- Issue reporting with validation, optional photos, map pin, optional address lookup, and nearby duplicate suggestions.
- Public issue details, ownership-aware editing/deletion, search, category/status/priority filters, sorting, and pagination.
- Community support, issue following, comments/updates, and in-app notifications.
- Staff-only operations at `/staff/` and Django admin at `/admin/`.
- Public Leaflet/OpenStreetMap issue map and basic analytics based on SQLite records.
- Basic Django REST Framework issue list, detail, create, and staff update endpoints.
- Optional AI Assist for improving report wording, suggesting a category, or making a short summary. The citizen reviews suggestions; AI never submits reports. The report form works without an API key.
- Contact form email delivery to the CivicFix team inbox, with a consistent CivicFix sender.
- Persistent user settings for locality, default issue category, time zone, language, appearance, and supported notification preferences.
- Private support tickets with staff replies, ticket status/priority management, and authorized screenshot access.
- Per-user watch areas with category matching and in-app alerts for new reports whose address contains the saved locality.
- Private JSON data export and password-confirmed account deletion requests for staff review; civic reports are not automatically removed.
- Responsive Bootstrap 5 interface and English, Hindi, and Odia localization.

## Technology

Python, Django 5.2, Django REST Framework, SQLite, HTML, CSS, Bootstrap 5, JavaScript, Leaflet/OpenStreetMap, Pillow, and python-dotenv. Optional AI Assist calls the OpenAI Responses API using Python's standard HTTP library.

## Run locally (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. SQLite is the default. No AI key or external database is required to run the project. Email uses Django's console backend until SMTP credentials are configured.

## Email configuration

The contact form sends submissions to `civicfix.team@gmail.com`. Password reset, email verification, and issue update mail use `CivicFix Team <civicfix.team@gmail.com>` as the sender. For real delivery, set `EMAIL_HOST_PASSWORD` in the local `.env` to a Gmail App Password for the CivicFix team account. Do not use a normal Gmail password and never commit `.env`. Without an App Password, mail is written to the runserver terminal so local development can continue.

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=civicfix.team@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=CivicFix Team <civicfix.team@gmail.com>
CONTACT_RECEIVER_EMAIL=civicfix.team@gmail.com
```

## Optional AI configuration

Set `OPENAI_API_KEY` in `.env` to enable AI Assist. `OPENAI_MODEL` defaults to `gpt-5-mini`. AI requests send only the report description, set `store: false`, and are optional. Never commit `.env` or an API key.

## Main URLs

- `/` — Home and recent reports
- `/signup/` — Create an account
- `/login/` — Sign in; citizens go to Home and staff go to Staff Operations
- `/issues/` — Search and browse reports
- `/report/` — Report an issue (login required)
- `/profile/` — Profile and report history (login required)
- `/settings/` — Personal preferences, privacy, watch areas, data export and support
- `/support/` — Your private support requests
- `/staff/support/` — Staff-only support queue and deletion-request review
- `/staff/` — Staff issue operations (staff only)
- `/notifications/` — In-app notification history (login required)
- `/map/` — Public issue map
- `/analytics/` — Public issue statistics
- `/about/` and `/contact/` — Product information and contact form
- `/api/issues/` — Paginated issue API
- `/api/issues/<id>/` — Issue details and permitted updates
- `/api/ai-assist/` — Authenticated optional AI helper used by the report form

## Authentication flow

Signup validates the account details and password, creates the account, and redirects to login with a confirmation message. Signup does not authenticate the new user. A normal citizen who signs in goes to Home; a staff user goes to Staff Operations. Password recovery uses Django's built-in flow.

