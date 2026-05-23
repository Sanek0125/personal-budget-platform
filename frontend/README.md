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

For local browser development, prefer Vite's `/api` proxy so requests stay same-origin and avoid CORS preflight issues. The proxy forwards `/api/*` to `http://localhost:8000/*`:

```bash
cd frontend
VITE_API_BASE_URL=/api \
VITE_DEV_USER_ID=<user-uuid> \
npm run dev
```

The backend also enables CORS for `http://localhost:5173` and `http://127.0.0.1:5173` by default, so direct API calls are supported when needed:

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 \
VITE_DEV_USER_ID=<user-uuid> \
npm run dev
```

If you add a `.env.local` later, use the proxy by default:

```text
VITE_API_BASE_URL=/api
VITE_DEV_USER_ID=<user-uuid>
```

The Settings page includes development-only helpers for the temporary auth phase:

- create a local user through `POST /users`;
- find a user by normalized email through `GET /users?email=...`;
- add the found user to the currently active workspace as `admin`, `member`, or `viewer`.

The Accounts page is the first functional MVP page beyond Settings. It uses the active workspace loaded through development auth to:

- list accounts from `GET /workspaces/{workspace_id}/accounts`;
- create cash, card, bank, bonus, investment, crypto, or other accounts through `POST /workspaces/{workspace_id}/accounts`;
- normalize the entered currency code to uppercase before sending it to the backend.

The Categories page connects the existing workspace-scoped categories API to:

- list categories from `GET /workspaces/{workspace_id}/categories`;
- create top-level `expense`, `income`, `transfer`, or `mixed` categories through `POST /workspaces/{workspace_id}/categories`;
- include optional display metadata such as color, icon, and sort order.

The Transactions page connects the manual-entry API to the existing workspace, accounts, and categories flows:

- list transactions from `GET /workspaces/{workspace_id}/transactions`;
- load account and category names for transaction context;
- create manual `expense`, `income`, or `adjustment` transactions through `POST /workspaces/{workspace_id}/transactions`;
- derive the transaction currency from the selected account and normalize expense amounts as negative values before sending.

The Budgets page connects the monthly planning API to the active workspace:

- list active budgets from `GET /workspaces/{workspace_id}/budgets`;
- create monthly budgets through `POST /workspaces/{workspace_id}/budgets`;
- normalize budget currency codes to uppercase and keep categories loaded for upcoming limit planning.

The Imports page connects the CSV import preview and confirmation flow to the active workspace:

- load target accounts from `GET /workspaces/{workspace_id}/accounts`;
- upload simple CSV statements through `POST /workspaces/{workspace_id}/imports/upload` using the default column mapping `Date`, `Amount`, `Currency`, and `Description`;
- preview normalized rows from `GET /workspaces/{workspace_id}/imports/{import_batch_id}/rows`;
- confirm parsed rows into transactions through `POST /workspaces/{workspace_id}/imports/{import_batch_id}/confirm`.

The Debts page connects the workspace debt tracking API to:

- list debts from `GET /workspaces/{workspace_id}/debts`;
- display direction/currency totals from `GET /workspaces/{workspace_id}/debts/summary`;
- create simple debts with a new contact name through `POST /workspaces/{workspace_id}/debts`;
- normalize debt currency codes to uppercase before sending them to the backend.

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
VITE_API_BASE_URL=/api \
VITE_DEV_USER_ID=<user-uuid> \
npm run dev
```

Then open http://localhost:5173.
