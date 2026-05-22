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
