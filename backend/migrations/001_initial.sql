-- HAQ initial schema. All money values are stored as TEXT decimals ("1234.50")
-- so that arithmetic is done with Python Decimal, never floats.

CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('worker', 'employer')),
    display_name    TEXT NOT NULL,
    phone           TEXT,
    business_name   TEXT,
    preferred_language TEXT NOT NULL DEFAULT 'en',
    email_verified_at TEXT,
    employer_verification TEXT NOT NULL DEFAULT 'unverified'
        CHECK (employer_verification IN ('unverified', 'pending', 'verified')),
    token_version   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE auth_codes (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    purpose     TEXT NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
    code_hash   TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_auth_codes_user ON auth_codes(user_id, purpose);

CREATE TABLE email_outbox (
    id          TEXT PRIMARY KEY,
    to_email    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('logged', 'sent', 'failed')),
    error       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE engagements (
    id              TEXT PRIMARY KEY,
    worker_id       TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    employer_name   TEXT NOT NULL,
    work_type       TEXT NOT NULL,
    pay_type        TEXT NOT NULL CHECK (pay_type IN ('daily','hourly','weekly','monthly','piece','task')),
    rate            TEXT NOT NULL,
    units           TEXT NOT NULL,
    payments_received TEXT NOT NULL DEFAULT '0',
    start_date      TEXT,
    end_date        TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX idx_engagements_worker ON engagements(worker_id, created_at);

CREATE TABLE claims (
    id              TEXT PRIMARY KEY,
    reference       TEXT NOT NULL UNIQUE,
    worker_id       TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status          TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    description     TEXT NOT NULL DEFAULT '',
    employer_name   TEXT,
    employer_email  TEXT COLLATE NOCASE,
    work_type       TEXT,
    start_date      TEXT,
    end_date        TEXT,
    amount_claimed  TEXT,
    requested_outcome TEXT,
    engagement_id   TEXT REFERENCES engagements(id) ON DELETE SET NULL,
    private_notes   TEXT,
    complaint_text  TEXT,
    complaint_provider TEXT,
    submitted_at    TEXT,
    submit_key      TEXT UNIQUE,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX idx_claims_worker ON claims(worker_id, updated_at);
CREATE INDEX idx_claims_employer_email ON claims(employer_email, status);

CREATE TABLE evidence (
    id              TEXT PRIMARY KEY,
    claim_id        TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    uploaded_by     TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    party           TEXT NOT NULL CHECK (party IN ('worker', 'employer')),
    message_id      TEXT,
    original_name   TEXT NOT NULL,
    kind            TEXT NOT NULL,
    mime_type       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    storage_name    TEXT NOT NULL UNIQUE,
    shared_with_employer INTEGER NOT NULL DEFAULT 0,
    extraction_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (extraction_status IN ('pending','done','failed','unsupported')),
    extracted_text  TEXT,
    extracted_text_edited INTEGER NOT NULL DEFAULT 0,
    extraction_error TEXT,
    found_amounts   TEXT,
    found_dates     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_evidence_claim ON evidence(claim_id);

CREATE TABLE complaint_versions (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    version     INTEGER NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('ai', 'template', 'worker')),
    provider    TEXT NOT NULL,
    model       TEXT,
    text        TEXT NOT NULL,
    structured  TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE (claim_id, version)
);

CREATE TABLE messages (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    author_id   TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    author_role TEXT NOT NULL CHECK (author_role IN ('worker', 'employer')),
    kind        TEXT NOT NULL CHECK (kind IN ('response','question','agree','dispute','reply')),
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_messages_claim ON messages(claim_id, created_at);

CREATE TABLE settlements (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    offered_by  TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount      TEXT NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'INR',
    explanation TEXT NOT NULL DEFAULT '',
    expires_on  TEXT,
    status      TEXT NOT NULL CHECK (status IN ('offered','accepted','rejected','superseded')),
    decided_at  TEXT,
    decision_note TEXT,
    request_key TEXT UNIQUE,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_settlements_claim ON settlements(claim_id);

CREATE TABLE payments (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    settlement_id TEXT REFERENCES settlements(id) ON DELETE RESTRICT,
    recorded_by TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount      TEXT NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'INR',
    paid_on     TEXT NOT NULL,
    reference   TEXT,
    receipt_evidence_id TEXT REFERENCES evidence(id) ON DELETE RESTRICT,
    worker_confirmation TEXT NOT NULL DEFAULT 'pending'
        CHECK (worker_confirmation IN ('pending','confirmed','disputed')),
    worker_note TEXT,
    request_key TEXT UNIQUE,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_payments_claim ON payments(claim_id);

CREATE TABLE claim_events (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    actor_id    TEXT REFERENCES users(id) ON DELETE RESTRICT,
    actor_role  TEXT NOT NULL,
    type        TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_events_claim ON claim_events(claim_id, created_at);

CREATE TABLE notifications (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    claim_id    TEXT REFERENCES claims(id) ON DELETE RESTRICT,
    type        TEXT NOT NULL,
    dedupe_key  TEXT NOT NULL UNIQUE,
    read_at     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_notifications_user ON notifications(user_id, created_at);

CREATE TABLE audit_log (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,
    action      TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    ip          TEXT,
    detail      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- Evidence and history are append-only records: block hard deletes at the database level.
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence records cannot be deleted'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON claim_events
BEGIN SELECT RAISE(ABORT, 'claim history cannot be deleted'); END;
CREATE TRIGGER claims_no_delete BEFORE DELETE ON claims
BEGIN SELECT RAISE(ABORT, 'claims cannot be deleted; withdraw instead'); END;
CREATE TRIGGER evidence_original_immutable BEFORE UPDATE OF sha256, storage_name, size_bytes, uploaded_by, claim_id ON evidence
BEGIN SELECT RAISE(ABORT, 'original evidence metadata is immutable'); END;
