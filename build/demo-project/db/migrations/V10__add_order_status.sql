-- Applied after V9, not after V1: migrations are ordered by number, not by the
-- alphabet. (A tool that sorts these as text runs V10 second and corrupts the
-- schema — which is why the map zero-pads before it sorts.)
ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'placed';

CREATE INDEX idx_orders_status ON orders (status);

CREATE VIEW open_orders AS
    SELECT id, customer_id, amount_cents, placed_at
    FROM orders
    WHERE status IN ('placed', 'authorized');
