-- Order Supervisor schema. Compatible with Postgres / Supabase.

create table if not exists supervisors (
    id                      uuid primary key default gen_random_uuid(),
    name                    text not null,
    base_instruction        text not null,
    available_actions       jsonb not null default '["message_fulfillment_team", "message_payments_team", "message_logistics_team", "message_customer", "create_internal_note"]',
    default_wake_policy     text not null default '',
    model_config            jsonb not null default '{"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2}',
    wake_aggressiveness     text not null default 'balanced', -- conservative | balanced | aggressive
    max_workflow_age_hours  integer,
    created_at              timestamptz not null default now()
);

create table if not exists runs (
    id                      uuid primary key default gen_random_uuid(),
    supervisor_id           uuid not null references supervisors (id),
    order_id                text not null,
    temporal_workflow_id    text not null unique,
    temporal_run_id         text,
    status                  text not null default 'active', -- active | sleeping | paused | completed | terminated
    memory_summary          text not null default '',
    wake_policy             text not null default '',
    next_wake_at            timestamptz,
    final_summary           text,
    final_learnings         text,
    final_feedback          text,
    -- Monotonic counter used to assign deterministic `run_activity_log.seq`
    -- values from inside the workflow (never DB-side now()/autoincrement,
    -- since concurrent activity fan-out gives no completion-order guarantee).
    seq_counter             integer not null default 0,
    epoch                   integer not null default 0, -- incremented on each continue_as_new
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),
    completed_at            timestamptz
);

create index if not exists idx_runs_supervisor_id on runs (supervisor_id);
create index if not exists idx_runs_status on runs (status);

-- Single append-only activity log covering everything the spec calls out:
-- incoming events, wake-up decisions, sleep decisions, agent actions,
-- manual instructions, and final outputs.
create table if not exists run_activity_log (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid not null references runs (id),
    seq         integer not null,
    kind        text not null, -- incoming_event | wake_decision | sleep_decision | agent_action | manual_instruction | final_output | system
    payload     jsonb not null default '{}',
    created_at  timestamptz not null default now(),
    unique (run_id, seq)
);

create index if not exists idx_run_activity_log_run_id_seq on run_activity_log (run_id, seq);

-- Cross-run long-term memory (a custom addition beyond anything the spec
-- asks for — see the README's "Custom addition" section). Stores
-- problem/resolution pairs extracted at run-finalization time, embedded for
-- semantic similarity search so a *future, unrelated* run can recall "a
-- similar issue happened before and this is how it was resolved."
--
-- The embedding is a plain Postgres double precision[] rather than a
-- pgvector column: pgvector isn't available for Postgres 14 (only 17+ at
-- the time this was written), and requiring reviewers to run a newer major
-- Postgres version just for this bonus feature would add real setup
-- friction. Cosine similarity is computed in the application layer instead
-- (see app/db/repository.py:find_similar_lessons) — entirely adequate at
-- the data volumes a POC produces, and swapping in pgvector later only
-- means changing that one function's internals, not its interface.
create table if not exists long_term_lessons (
    id              uuid primary key default gen_random_uuid(),
    supervisor_id   uuid references supervisors (id),
    source_run_id   uuid references runs (id),
    order_id        text not null,
    event_type      text, -- best-effort tag for display only, not used for retrieval
    problem         text not null,
    resolution      text not null,
    embedding       double precision[] not null,
    -- 'agent': auto-extracted by the wrap-up LLM call at run finalization.
    -- 'human': manually logged from the UI against a specific timeline
    -- entry — see the README's "Custom addition" section.
    source          text not null default 'agent',
    fault           text, -- 'internal' | 'client', human-entries only
    created_at      timestamptz not null default now()
);

create index if not exists idx_long_term_lessons_created_at on long_term_lessons (created_at);
