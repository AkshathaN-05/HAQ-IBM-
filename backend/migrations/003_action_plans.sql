-- For problems that are not about money (safety, harassment, threats, unfair treatment, co-workers),
-- the employer proposes concrete actions instead of a payment. The worker agrees, the employer marks
-- them done, and the claim closes only when the worker confirms the actions really happened.
CREATE TABLE action_plans (
    id            TEXT PRIMARY KEY,
    claim_id      TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    proposed_by   TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    actions       TEXT NOT NULL,              -- JSON list of action keys chosen by the employer
    custom_action TEXT,
    contact_name  TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    due_on        TEXT,
    note          TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL CHECK (status IN ('proposed','accepted','rejected','superseded','done')),
    decided_at    TEXT,
    decision_note TEXT,
    done_at       TEXT,
    done_note     TEXT,
    worker_confirmation TEXT NOT NULL DEFAULT 'pending' CHECK (worker_confirmation IN ('pending','confirmed','disputed')),
    worker_note   TEXT,
    request_key   TEXT UNIQUE,
    created_at    TEXT NOT NULL
);
CREATE INDEX idx_action_plans_claim ON action_plans(claim_id);
