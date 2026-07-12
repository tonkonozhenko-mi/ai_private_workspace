-- Following a foreign key without an index means a sequential scan per lookup.
CREATE INDEX idx_orders_customer_id ON orders (customer_id);
CREATE INDEX idx_orders_placed_at ON orders (placed_at);
