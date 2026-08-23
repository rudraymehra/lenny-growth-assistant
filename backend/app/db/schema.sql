-- Idempotent schema, applied by the backend on startup.
-- Deliberate choice over a migration framework for this engagement: one file,
-- reviewable in a single read, safe to re-apply. See architecture.md#schema.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sessions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title          text NOT NULL DEFAULT 'New conversation',
  provider       text NOT NULL CHECK (provider IN ('anthropic', 'local')),
  model          text NOT NULL,
  sdk_session_id text,                          -- Claude Agent SDK resume handle
  user_metadata  jsonb NOT NULL DEFAULT '{}',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifacts (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  kind              text NOT NULL CHECK (kind IN ('markdown', 'html')),
  title             text NOT NULL,
  content           text NOT NULL,              -- exactly as generated (audit)
  sanitized_content text NOT NULL,              -- what the viewer renders
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role        text NOT NULL CHECK (role IN ('user', 'assistant')),
  content     text NOT NULL,
  citations   jsonb NOT NULL DEFAULT '[]',
  artifact_id uuid REFERENCES artifacts(id) ON DELETE SET NULL,
  usage       jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS episodes (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug         text UNIQUE NOT NULL,
  guest        text NOT NULL,
  title        text NOT NULL,
  youtube_url  text,
  video_id     text,
  publish_date date,
  description  text,
  keywords     text[] NOT NULL DEFAULT '{}',
  content_hash text NOT NULL,                   -- sha256 of source file → idempotent ingest
  chunk_count  int NOT NULL DEFAULT 0,
  ingested_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id          bigserial PRIMARY KEY,
  episode_id  uuid NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  chunk_index int NOT NULL,
  speaker     text,
  start_ts    int NOT NULL,                     -- seconds → {youtube_url}&t={start_ts}
  end_ts      int NOT NULL,
  content     text NOT NULL,
  token_count int NOT NULL,
  embedding   vector(384) NOT NULL,
  tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  UNIQUE (episode_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING gin(tsv);
-- ~10k chunks total (303 episodes × ~30): HNSW is cheap to build and keeps
-- vector queries sub-millisecond.
CREATE INDEX IF NOT EXISTS idx_chunks_vec ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz,
  status           text NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'succeeded', 'failed')),
  episodes_seen    int NOT NULL DEFAULT 0,
  episodes_written int NOT NULL DEFAULT 0,
  episodes_skipped int NOT NULL DEFAULT 0,
  chunks_written   int NOT NULL DEFAULT 0,
  error            text
);
