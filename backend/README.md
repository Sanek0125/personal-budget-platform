# Personal Budget Backend

FastAPI backend for the Personal Budget Platform.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker + Docker Compose for PostgreSQL

## Local setup

From the repository root:

```bash
cd backend
cp .env.example .env
uv sync
```

Start PostgreSQL from the repository root:

```bash
cd /path/to/personal-budget-platform
docker compose -f infra/docker-compose.yml up -d postgres
```

Apply database migrations:

```bash
cd backend
uv run alembic upgrade head
```

Run the API server:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

The backend will be available at:

- API: http://localhost:8000
- Health check: http://localhost:8000/health
- OpenAPI docs: http://localhost:8000/docs

## Database connection

Default local database settings from `.env.example` and Docker Compose:

```text
host: localhost
port: 5432
database: budget
user: budget
password: budget
```

Connect with psql inside the Docker container:

```bash
docker exec -it personal-budget-postgres psql -U budget -d budget
```

Useful psql commands:

```sql
\dt
SELECT * FROM users LIMIT 10;
SELECT * FROM workspaces LIMIT 10;
SELECT * FROM accounts LIMIT 10;
SELECT * FROM transactions LIMIT 10;
\q
```

## Authentication and workspace members

The backend now supports bearer-token authentication for normal browser/API use:

```bash
# Register a user and receive an access token.
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"vasily@example.com","password":"change-me-please","display_name":"Василий"}'

# Log in an existing password user.
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"vasily@example.com","password":"change-me-please"}'

# Fetch the current user. Use the access_token returned by register/login.
curl -s http://localhost:8000/auth/me \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

Workspace-scoped routes derive the requester from the `Authorization` bearer token and return `401` when no credentials are provided. The previous `X-User-Id` header remains available only as an explicit local/dev fallback while the frontend auth gate is being built.

Create users and add them to a workspace through HTTP instead of direct SQL:

```bash
# Create a user
curl -s -X POST http://localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"vasily@example.com","display_name":"Василий"}'

# Add an existing user to a workspace as admin/member/viewer.
# The bearer token must belong to a current workspace owner or admin.
curl -s -X POST http://localhost:8000/workspaces/<workspace-id>/members \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer OWNER_OR_ADMIN_ACCESS_TOKEN' \
  -d '{"user_id":"<new-user-id>","role":"member"}'
```

For local development scripts that have not moved to `/auth/login` yet, use the created user's UUID in the frontend with `VITE_DEV_USER_ID`.

## Checks

Run backend formatting/lint checks and tests:

```bash
cd backend
uv run ruff check .
uv run pytest -q
```

Verify migrations against PostgreSQL:

```bash
cd /path/to/personal-budget-platform
docker compose -f infra/docker-compose.yml up -d postgres
cd backend
uv run alembic downgrade base
uv run alembic upgrade head
```

## Docker Compose backend service

Docker Compose also contains a backend service. To run PostgreSQL and backend together:

```bash
cd /path/to/personal-budget-platform
docker compose -f infra/docker-compose.yml up --build backend
```

This starts the backend on http://localhost:8000.
