### 1. Stack Decision
FastAPI + SQLAlchemy + SQLite (default) + Jinja/Vanilla JS + Docker + Railway. This stack is optimal for speed-to-deploy because it needs minimal infrastructure, supports full-stack delivery from one codebase, and deploys directly from a Dockerfile with near-zero platform wiring.

### 2. Data Model
`users`
- `id` INTEGER PK
- `username` VARCHAR(64) UNIQUE NOT NULL
- `full_name` VARCHAR(120) NOT NULL
- `password_hash` VARCHAR(255) NOT NULL
- `role` ENUM(`admin`,`manager`,`viewer`) NOT NULL
- `api_key` VARCHAR(120) UNIQUE NOT NULL
- `is_active` BOOLEAN NOT NULL DEFAULT true
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

`items`
- `id` INTEGER PK
- `sku` VARCHAR(64) UNIQUE NOT NULL
- `name` VARCHAR(255) NOT NULL
- `category` VARCHAR(120) NOT NULL
- `details` TEXT NULL
- `quantity` INTEGER NOT NULL DEFAULT 0
- `reorder_threshold` INTEGER NOT NULL DEFAULT 10
- `unit_cost` FLOAT NOT NULL DEFAULT 0
- `status` ENUM(`in_stock`,`low_stock`,`ordered`,`discontinued`) NOT NULL
- `is_deleted` BOOLEAN NOT NULL DEFAULT false
- `created_by_id` FK -> `users.id`
- `updated_by_id` FK -> `users.id`
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

`quantity_events`
- `id` INTEGER PK
- `item_id` FK -> `items.id` NOT NULL
- `event_type` ENUM(`inbound`,`outbound`,`adjustment`) NOT NULL
- `quantity_before` INTEGER NOT NULL
- `quantity_delta` INTEGER NOT NULL
- `quantity_after` INTEGER NOT NULL
- `note` TEXT NULL
- `actor_user_id` FK -> `users.id`
- `created_at` DATETIME NOT NULL

`audit_logs`
- `id` INTEGER PK
- `entity_type` VARCHAR(64) NOT NULL
- `entity_id` INTEGER NULL
- `action` VARCHAR(64) NOT NULL
- `before_state` TEXT NULL
- `after_state` TEXT NULL
- `note` TEXT NULL
- `actor_user_id` FK -> `users.id`
- `created_at` DATETIME NOT NULL

Relationships
- `users` 1:N `items` via `created_by_id`, `updated_by_id`
- `items` 1:N `quantity_events`
- `users` 1:N `quantity_events`
- `users` 1:N `audit_logs`

RBAC
- `admin`: full access including user role management
- `manager`: inventory CRUD/status/search/AI/audit read, no user management
- `viewer`: read-only inventory/search/dashboard/audit/AI

### 3. API Surface
Public
- `GET /` -> HTML app shell
- `GET /health` -> `{ "status": "ok" }`
- `POST /api/auth/login` -> body `{ username, password }`; response `{ api_key, user }`; auth: public

User/RBAC
- `GET /api/me` -> current user profile; auth: admin/manager/viewer
- `GET /api/users` -> list users; auth: admin
- `PATCH /api/users/{user_id}/role` -> body `{ role }`; returns user; auth: admin

Inventory CRUD
- `POST /api/items` -> body `{ sku,name,category,details,quantity,reorder_threshold,unit_cost,status? }`; returns item; auth: admin/manager
- `GET /api/items` -> query filters (`q,category,status,min_qty,max_qty,include_deleted,sort_by,sort_dir,page,page_size`); returns `{ items,total,page,page_size }`; auth: admin/manager/viewer
- `GET /api/items/{item_id}` -> item; auth: admin/manager/viewer
- `PUT /api/items/{item_id}` -> partial item update body; returns item; auth: admin/manager
- `DELETE /api/items/{item_id}` -> soft delete; returns `{ id, is_deleted }`; auth: admin/manager

Search
- `GET /api/items/search` -> query (`q,category,status,min_qty,max_qty,page,page_size`); returns `{ items,total,page,page_size }`; auth: admin/manager/viewer

Status Management
- `PATCH /api/items/{item_id}/status` -> body `{ status, note? }`; returns item; auth: admin/manager
- `PATCH /api/items/status/bulk` -> body `{ item_ids[], status, note? }`; returns `{ updated_count,status,item_ids }`; auth: admin/manager
- `POST /api/items/{item_id}/quantity` -> body `{ event_type, quantity_delta, note? }`; returns item; auth: admin/manager

Analytics/Audit
- `GET /api/audit` -> query `limit`; returns audit list; auth: admin/manager/viewer
- `GET /api/dashboard` -> KPI summary, category split, recent activity; auth: admin/manager/viewer

AI Features
- `GET /api/ai/reorder-suggestions` -> query `limit`; returns `{ source, model, suggestions[] }`; auth: admin/manager/viewer
- `GET /api/ai/anomaly-alerts` -> query `days,limit`; returns `{ source, model, alerts[] }`; auth: admin/manager/viewer
- `POST /api/ai/natural-language-search` -> body `{ query }`; returns `{ source, model, parsed_filters, items[] }`; auth: admin/manager/viewer

Validation + errors
- Pydantic schema validation for body/query
- HTTP 401 unauthorized, 403 forbidden, 404 missing resource, 409 conflict, 422 validation
- Every database write creates `audit_logs` entry

### 4. AI Features (minimum 2)
Feature 1: Reorder Copilot
- What: ranks reorder suggestions using quantity/threshold policy and optional AI-generated rationale
- Model/API: OpenAI Responses API (`OPENAI_MODEL`, default `gpt-4.1-mini`)
- UI location: AI Insights > Reorder Copilot table
- Fallback: deterministic local ranking and reason text when API unavailable

Feature 2: Anomaly Alerts
- What: detects unusual quantity movements and proposes action text
- Model/API: OpenAI Responses API for explanation enrichment
- UI location: AI Insights > Anomaly Alerts panel
- Fallback: statistical threshold rule-based detection

Feature 3: Natural Language Search
- What: converts plain-English intent into structured filters
- Model/API: OpenAI Responses API parser
- UI location: Search view > AI Natural Language Search
- Fallback: regex-based parser (category/status/quantity phrases)

### 5. File Map
Database
- `migrations/001_schema.sql`: SQL schema for users/items/quantity_events/audit_logs
- `app/models.py`: SQLAlchemy entity definitions and enums
- `app/database.py`: engine/session configuration
- `app/seed.py`: seed users/items/events/audits

Backend
- `app/main.py`: route handlers, validation wiring, RBAC dependencies, audit integration
- `app/auth.py`: auth primitives, role guard, password hashing/verification
- `app/schemas.py`: API request/response contracts
- `app/services/ai_features.py`: AI + fallback logic

Frontend
- `app/templates/index.html`: root HTML template
- `app/templates/components/layout.html`: shell/sidebar/header
- `app/templates/components/dashboard.html`: KPI and activity UI
- `app/templates/components/inventory-list.html`: table/filter/bulk UI
- `app/templates/components/item-form-modal.html`: create/edit modal
- `app/templates/components/search.html`: standard + NL search UI
- `app/templates/components/ai-features.html`: reorder/anomaly UI
- `app/templates/components/auth.html`: login UI
- `app/static/app.js`: client state/actions/fetch/UX states
- `app/static/styles.css`: responsive design and visual system

Config
- `.env.example`: required env vars and descriptions
- `requirements.txt`: pinned dependencies
- `Dockerfile`: container build/run
- `railway.toml`: Railway deploy config
- `README.md`: run/deploy instructions and demo credentials

## Self-Audit
1. PASS: Data model covers CRUD fields + status + roles (see Section 2 and `app/models.py`).
2. PASS: API covers CRUD + search + status update + AI features (see Section 3 and `app/main.py`).
3. PASS: AI features include fallback behavior (see Section 4 and `app/services/ai_features.py`).
4. PASS: File map is explicit and implementation-complete (see Section 5).
5. PASS: Every protected endpoint has auth level specified (Section 3 + role guards in `app/main.py`).
