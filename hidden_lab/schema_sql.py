"""Schema immutabile delle migrazioni: nessun SQL ricevuto dai client."""

CORE_SQL = """
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY, record_json TEXT NOT NULL, manifest_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
                    agent_token_hash TEXT NOT NULL, score_json TEXT, audit_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL REFERENCES sessions(id), seq INTEGER NOT NULL,
                    actor TEXT NOT NULL, message_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, seq)
                );
                CREATE TABLE IF NOT EXISTS session_profiles (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id), profile_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY, human_id TEXT NOT NULL REFERENCES sessions(id),
                    agent_id TEXT NOT NULL REFERENCES sessions(id), rules_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_worlds (
                    day TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id)
                );
                CREATE TABLE IF NOT EXISTS agent_calls (
                    session_id TEXT NOT NULL REFERENCES sessions(id), call_index INTEGER NOT NULL,
                    outcome TEXT NOT NULL, audit_json TEXT NOT NULL,
                    PRIMARY KEY(session_id, call_index)
                );
            """

ARENA_SQL = """
                CREATE TABLE IF NOT EXISTS arena_agents (
                    id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL, quotas_json TEXT NOT NULL,
                    sessions INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 0,
                    experiments INTEGER NOT NULL DEFAULT 0, invalid INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS arena_tokens (
                    id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES arena_agents(id),
                    hash TEXT NOT NULL UNIQUE, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS arena_challenges (
                    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
                    name TEXT NOT NULL, rules_json TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS arena_trials (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
                    challenge_id TEXT NOT NULL REFERENCES arena_challenges(id),
                    agent_id TEXT NOT NULL REFERENCES arena_agents(id), cohort_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS arena_receipts (
                    principal TEXT NOT NULL, key_hash TEXT NOT NULL, path TEXT NOT NULL,
                    body_hash TEXT NOT NULL, status INTEGER NOT NULL, response_json TEXT NOT NULL,
                    PRIMARY KEY(principal,key_hash));
                CREATE TABLE IF NOT EXISTS arena_audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL, principal TEXT NOT NULL,
                    action TEXT NOT NULL, status INTEGER NOT NULL, key_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS arena_rates (
                    agent_id TEXT PRIMARY KEY REFERENCES arena_agents(id), window REAL NOT NULL,
                    reads INTEGER NOT NULL DEFAULT 0, writes INTEGER NOT NULL DEFAULT 0);
            """

INTEGRITY_SQL = """
        CREATE TABLE IF NOT EXISTS integrity_packs (
            id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, private_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS integrity_cases (
            id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES integrity_packs(id),
            split TEXT NOT NULL, record_json TEXT NOT NULL, fingerprint_json TEXT NOT NULL,
            disclosed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS integrity_flags (
            session_id TEXT NOT NULL REFERENCES sessions(id), reason TEXT NOT NULL,
            PRIMARY KEY(session_id,reason));
    """

IDENTITY_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, handle TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1, key_hash TEXT NOT NULL UNIQUE,
    key_expires REAL NOT NULL, quotas_json TEXT NOT NULL,
    sessions INTEGER NOT NULL DEFAULT 0, experiments INTEGER NOT NULL DEFAULT 0,
    model_calls INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS account_sessions (
    hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
    expires REAL NOT NULL, last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS session_owners (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id), account_id TEXT NOT NULL REFERENCES accounts(id));
CREATE TABLE IF NOT EXISTS arena_owners (
    agent_id TEXT PRIMARY KEY REFERENCES arena_agents(id), account_id TEXT NOT NULL REFERENCES accounts(id));
CREATE TABLE IF NOT EXISTS account_rates (
    principal TEXT NOT NULL, bucket TEXT NOT NULL, window REAL NOT NULL, count INTEGER NOT NULL,
    PRIMARY KEY(principal,bucket));
CREATE TABLE IF NOT EXISTS account_audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL, actor TEXT NOT NULL,
    action TEXT NOT NULL, target TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS account_sessions_by_owner ON account_sessions(account_id);
CREATE INDEX IF NOT EXISTS sessions_by_owner ON session_owners(account_id);
"""

PUBLIC_WORKSPACE_SQL = """
CREATE TABLE IF NOT EXISTS account_passwords (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id), salt TEXT NOT NULL,
    password_hash TEXT NOT NULL, recovery_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_connections (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
    label TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, transport TEXT NOT NULL,
    secret BLOB, connector_hash TEXT UNIQUE, enabled INTEGER NOT NULL DEFAULT 1,
    last_seen REAL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ai_preferences (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id), connection_id TEXT REFERENCES ai_connections(id));
CREATE TABLE IF NOT EXISTS connector_jobs (
    id TEXT PRIMARY KEY, connection_id TEXT NOT NULL REFERENCES ai_connections(id),
    status TEXT NOT NULL, deadline REAL NOT NULL, request_json TEXT, reply_json TEXT, lease TEXT);
CREATE INDEX IF NOT EXISTS connector_jobs_by_connection ON connector_jobs(connection_id,status);
CREATE TABLE IF NOT EXISTS workspace_worlds (
    world_id TEXT PRIMARY KEY REFERENCES worlds(id), account_id TEXT NOT NULL REFERENCES accounts(id));
"""
