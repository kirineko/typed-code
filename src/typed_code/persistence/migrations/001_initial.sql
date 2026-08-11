-- Initial typed-code schema. Snapshots are computed from durable rows;
-- events support replay/audit and are not the sole source of truth.
-- transcript_items holds public-normalized transcript for snapshots;
-- model_messages holds server-private model history blobs.

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    workspace_path TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    phase TEXT NOT NULL,
    active_run_id TEXT,
    revision INTEGER NOT NULL,
    latest_event_sequence INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE INDEX idx_runs_session_id ON runs(session_id);
CREATE INDEX idx_runs_status ON runs(status);

CREATE TABLE model_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    position INTEGER NOT NULL,
    role TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, position)
);

CREATE INDEX idx_model_messages_session_position ON model_messages(session_id, position);

-- Public-normalized transcript for authoritative snapshots (not Pydantic AI types).
CREATE TABLE transcript_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, position)
);

CREATE INDEX idx_transcript_items_session_position ON transcript_items(session_id, position);

CREATE TABLE events (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    run_id TEXT,
    type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, sequence)
);

CREATE INDEX idx_events_session_sequence ON events(session_id, sequence);

CREATE TABLE approvals (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    tool_call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX idx_approvals_session_status ON approvals(session_id, status);

CREATE TABLE history_archives (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    archive_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_history_archives_session ON history_archives(session_id);
