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
