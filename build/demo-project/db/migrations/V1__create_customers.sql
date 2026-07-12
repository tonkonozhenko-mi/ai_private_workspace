-- The first thing the platform ever knew about: who is paying.
CREATE TABLE customers (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    country       CHAR(2) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
