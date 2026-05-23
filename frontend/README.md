# Personal Budget Frontend

React + TypeScript + Vite frontend for the Personal Budget Platform.

## Requirements

- Node.js `^20.19.0` or `>=22.12.0`
- npm 10+

The frontend can run by itself, but most useful flows expect the backend API to be running on http://localhost:8000.

## Local setup

From the repository root:

```bash
cd frontend
npm install
```

Run the development server:

```bash
cd frontend
npm run dev
```

The frontend will be available at the URL printed by Vite, usually:

```text
http://localhost:5173
```

## Backend API URL and development auth

By default, the API client uses root-relative URLs and sends the temporary development auth header required by the backend:

```text
X-User-Id: 00000000-0000-0000-0000-000000000001
```

To point the frontend at the local backend and use a seeded/local user, set `VITE_API_BASE_URL` and `VITE_DEV_USER_ID` when starting Vite:

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 \
VITE_DEV_USER_ID=<user-uuid> \
npm run dev
```

If you add a `.env.local` later, use:

```text
VITE_API_BASE_URL=http://localhost:8000
VITE_DEV_USER_ID=<user-uuid>
```

The Settings page includes development-only helpers for the temporary auth phase:

- create a local user through `POST /users`;
- find a user by normalized email through `GET /users?email=...`;
- add the found user to the currently active workspace as `admin`, `member`, or `viewer`.

## Available scripts

```bash
npm run dev        # start Vite dev server
npm run build      # type-check and build production assets
npm test           # run Vitest tests once
npm run test:watch # run Vitest in watch mode
npm run lint       # run ESLint
```

## Checks

Before opening or updating a PR, run:

```bash
cd frontend
npm test
npm run build
npm run lint
```

## Run frontend and backend together locally

Terminal 1 — backend database and API:

```bash
cd /path/to/personal-budget-platform
docker compose -f infra/docker-compose.yml up -d postgres
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Terminal 2 — frontend:

```bash
cd /path/to/personal-budget-platform/frontend
VITE_API_BASE_URL=http://localhost:8000 \
VITE_DEV_USER_ID=<user-uuid> \
npm run dev
```

Then open http://localhost:5173.
