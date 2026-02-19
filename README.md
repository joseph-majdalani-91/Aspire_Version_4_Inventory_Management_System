# Independent AI Inventory Management System

A production-ready inventory management web app with RBAC, audit trails, advanced search, and resilient AI copilots.

## Live Demo URL

`https://giant-drinks-make.loca.lt` (active temporary live URL for evaluator testing)

## Tech Stack (Pinned)

- Python `3.13`
- FastAPI `0.128.0`
- Uvicorn `0.40.0`
- SQLAlchemy `2.0.46`
- Jinja2 `3.1.6`
- python-dotenv `1.0.1`
- OpenAI SDK `1.68.2`
- NumPy `2.2.3`
- pandas `2.2.3`
- scikit-learn `1.6.1`

## Setup (Clone to Run in <=5 Commands)

```bash
git clone <YOUR_REPO_URL>
cd "Inventory Management System"
python3 -m venv .venv
source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env
python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open: `http://127.0.0.1:8000`

Temporary public URL (free, ephemeral): run `./scripts/run_public_tunnel.sh` and use the printed `https://*.loca.lt` URL.

## Deploy (Railway, <=5 Commands)

```bash
npm install -g @railway/cli
railway login
railway init
railway variables set AUTH_PASSWORD_PEPPER="replace-with-strong-secret" AUTH_PASSWORD_ITERATIONS="210000" OPENAI_MODEL="gpt-4.1-mini"
railway up && railway open
```

Railway reads `Dockerfile` / `railway.toml` and returns a public URL.

## Default Credentials (Demo Login)

- `admin` / `admin123`
- `manager` / `manager123`
- `viewer` / `viewer123`

## Features

- **Item CRUD**: create, update, soft delete inventory items with SKU uniqueness checks.
- **Status tracking**: `in_stock`, `low_stock`, `ordered`, `discontinued` with single and bulk updates.
- **Inventory search**: free-text, category, status, min/max quantity filters.
- **Role-based access control**: admin full access, manager operational control, viewer read-only.
- **Audit trail**: every database write logs before/after state with actor attribution.
- **Responsive UI**: split into layout/auth/dashboard/inventory/search/AI/modal components.

## AI Features

- **Reorder Copilot** (`GET /api/ai/reorder-suggestions`)
  - Uses OpenAI Responses API (`OPENAI_MODEL`, default `gpt-4.1-mini`) to enrich reorder rationales.
  - Fallback: deterministic reorder calculation and local reason text if AI is unavailable.
- **Anomaly Alerts** (`GET /api/ai/anomaly-alerts`)
  - Uses OpenAI Responses API to explain unusual quantity movements and suggest actions.
  - Fallback: statistical threshold detection with rule-based explanations.
- **Natural Language Search** (`POST /api/ai/natural-language-search`)
  - Uses OpenAI to parse search intent into structured filters.
  - Fallback: local regex parser for category/status/quantity constraints.

## Architecture Overview

This app is an independent FastAPI service backed by local SQLite by default (`ims_independent.db`) and has no dependency on Ampliphi or Supabase infrastructure. Authentication is API-key based after login and enforced through role guards on every protected endpoint. Item lifecycle changes (create/update/delete/status/quantity changes and user role updates) write to `audit_logs` for complete traceability. The frontend is a responsive Jinja + vanilla JS interface with explicit loading, empty, error, and success states across workflows. AI endpoints are fail-safe: they try OpenAI first and gracefully fall back to deterministic local logic when the AI provider is unavailable.
