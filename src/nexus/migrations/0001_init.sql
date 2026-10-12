CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_instances (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  product TEXT NOT NULL,
  account_alias TEXT NOT NULL,
  import_mode TEXT NOT NULL DEFAULT 'manual',
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  last_sync_at TEXT,
  sync_state TEXT NOT NULL DEFAULT 'never',
  UNIQUE(provider, product, account_alias)
);
CREATE TABLE IF NOT EXISTS import_batches (
  id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES source_instances(id),
  import_hash TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  counts_json TEXT NOT NULL DEFAULT '{}',
  errors_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  repo_url TEXT,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  sharing_policy TEXT NOT NULL DEFAULT 'none',
  archived_at TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_instances(id),
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'chat',
  title TEXT NOT NULL,
  project_id TEXT REFERENCES projects(id),
  first_at TEXT,
  last_at TEXT,
  coverage TEXT NOT NULL DEFAULT 'manual_import',
  UNIQUE(source_id, external_id)
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  external_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  occurred_at TEXT,
  observed_at TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  UNIQUE(conversation_id, external_id)
);
CREATE TABLE IF NOT EXISTS source_events (
  id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES source_instances(id),
  external_event_key TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT,
  observed_at TEXT NOT NULL,
  raw_ref TEXT,
  source_uri TEXT,
  UNIQUE(source_id, external_event_key)
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  title TEXT NOT NULL,
  objective TEXT NOT NULL DEFAULT '',
  acceptance_json TEXT NOT NULL DEFAULT '[]',
  state TEXT NOT NULL DEFAULT 'proposed',
  user_priority TEXT NOT NULL DEFAULT 'normal'
);
CREATE TABLE IF NOT EXISTS evidence_links (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  source_event_id TEXT REFERENCES source_events(id),
  source_uri TEXT,
  confidence TEXT NOT NULL DEFAULT 'source_reported'
);
CREATE TABLE IF NOT EXISTS sync_cursors (
  source_id TEXT PRIMARY KEY REFERENCES source_instances(id),
  adapter_version TEXT NOT NULL,
  cursor TEXT,
  last_success_at TEXT,
  backoff_until TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  target TEXT NOT NULL,
  outcome TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
  message_id UNINDEXED,
  title,
  content,
  tokenize = 'trigram'
);
CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
  INSERT INTO message_search(message_id, title, content)
  VALUES (new.id, (SELECT title FROM conversations WHERE id=new.conversation_id), new.content);
END;
