-- Independent Inventory Management System schema
-- Local-only schema, not connected to Ampliphi/Supabase.

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username VARCHAR(64) UNIQUE NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  password_hash VARCHAR(128) NOT NULL,
  role VARCHAR(16) NOT NULL CHECK (role IN ('admin', 'manager', 'viewer')),
  api_key VARCHAR(120) UNIQUE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(120) NOT NULL,
  details TEXT,
  quantity INTEGER NOT NULL DEFAULT 0,
  reorder_threshold INTEGER NOT NULL DEFAULT 10,
  unit_cost FLOAT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL CHECK (status IN ('in_stock', 'low_stock', 'ordered', 'discontinued')),
  is_deleted BOOLEAN NOT NULL DEFAULT 0,
  created_by_id INTEGER,
  updated_by_id INTEGER,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY (created_by_id) REFERENCES users (id),
  FOREIGN KEY (updated_by_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS quantity_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  event_type VARCHAR(16) NOT NULL CHECK (event_type IN ('inbound', 'outbound', 'adjustment')),
  quantity_before INTEGER NOT NULL,
  quantity_delta INTEGER NOT NULL,
  quantity_after INTEGER NOT NULL,
  note TEXT,
  actor_user_id INTEGER,
  created_at DATETIME NOT NULL,
  FOREIGN KEY (item_id) REFERENCES items (id),
  FOREIGN KEY (actor_user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type VARCHAR(64) NOT NULL,
  entity_id INTEGER,
  action VARCHAR(64) NOT NULL,
  before_state TEXT,
  after_state TEXT,
  note TEXT,
  actor_user_id INTEGER,
  created_at DATETIME NOT NULL,
  FOREIGN KEY (actor_user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_sku ON items(sku);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_quantity_events_created_at ON quantity_events(created_at);
