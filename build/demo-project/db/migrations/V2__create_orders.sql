-- Orders belong to a customer. The foreign key is declared here; the index that
-- makes it cheap to follow arrives in V3 — which is exactly the gap the map
-- should notice if V3 is ever rolled back.
CREATE TABLE orders (
    id            BIGSERIAL PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customers (id),
    amount_cents  BIGINT NOT NULL,
    currency      CHAR(3) NOT NULL DEFAULT 'EUR',
    placed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only audit log: deliberately has no primary key, because rows are never
-- addressed individually. A tool that calls this a defect is guessing; the map
-- states it as a fact to check.
CREATE TABLE order_events (
    order_id      BIGINT NOT NULL REFERENCES orders (id),
    event         TEXT NOT NULL,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
