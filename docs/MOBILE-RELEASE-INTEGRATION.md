# Mobile release integration fixes

These changes require deploying this backend revision and applying migrations.
No production deploy or production data writes were performed during development.

## Contract

- `POST /api/token/refresh/`: SimpleJWT `{refresh}` -> `{access}`; invalid or expired refresh -> 401.
- `GET /api/plan/categories/`: authenticated array of `{id,name,description}` from actual database rows. Only categories with tasks for all seven days are offered.
- `GET /api/plan/daily`: adds `category`, `category_id`, and `total_days` to the existing day/title/description/is_completed response. No active task returns 404.
- `POST /api/plan/activate/<category_id>`: rejects unavailable/incomplete categories with 404; account activation is atomic.
- `GET /api/specialist/waitlist/`: authenticated `{registered,registration}`; registration is null or `{id,name,contact,focus,created_at}`.
- `POST /api/specialist/waitlist/`: authenticated `{name,contact,focus}` -> same registration response, status 200; one row per account, repeat calls update it.
- `DELETE /api/specialist/waitlist/`: authenticated, account-owned cancel, 204 (also when already absent).
- `POST /api/community/posts/<post_id>/report/`: authenticated optional `{reason}` (max1000) -> `{message,reported:true}`. Report is idempotent per account/post, visible to staff in Django admin; the reporter's feed excludes it across devices.

`focus` uses the five existing mobile choices: Anxiety & Panic; Depression & Low Mood;
Sleep & Insomnia; Relationship & Family Stress; General Mental Wellness.

## Migrations

- 0005 adds specialist waitlist registrations and community reports, with ownership constraints.
- 0006 inserts missing Android/iOS baseline version records (latest/minimum 1.0.0,
  force_update false). It never overwrites existing operator-managed version data.
  Its reverse intentionally leaves version configuration intact.

Docker's existing startup command runs migrations. Procfile-based deployments must
run `python manage.py migrate --noinput` from `core` as a pre-deploy step.
After deploy, verify both version-check endpoints and an authenticated categories
request. An empty categories response means no complete seven-day category exists;
review existing seed content before running the existing clinical seed command.

## Local verification without production writes

From this backend root:

```
DATABASE_URL=sqlite:////tmp/serenio-release-tests.sqlite3 .venv/bin/python core/manage.py test chat users --noinput
DATABASE_URL=sqlite:////tmp/serenio-schema-check.sqlite3 .venv/bin/python core/manage.py makemigrations --check --dry-run
```

Django uses its isolated test database for the suite. For a local integration
server, use a separate temporary SQLite DATABASE_URL, migrate, create dedicated
local fixture users/tasks, and run `core/manage.py runserver --noreload` with
DJANGO_DEBUG=true and DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver in that
process's environment. Never use production database credentials for these writes.

Additional fixes: OAuth redirect logs omit token query/fragment data. Existing
medical-symptom routing now also recognizes "pain in my chest" and "cannot
breathe"; the existing medical-check response policy remains unchanged.
