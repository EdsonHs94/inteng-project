# Inventory service

Apply the existing Alembic migrations through `0002` before using reservations.

```http
POST /reservations HTTP/1.1
Content-Type: application/json

{"order_id":"6dcf531e-df12-457a-9d2c-e54b3b933174","inventory_id":"104a9f12-736e-4ec2-842e-1abb5bc9c663","quantity":3}
```

A successful request returns 201 with the reservation ID, order ID, inventory ID,
quantity, `RESERVED` status, and creation and update timestamps. A missing
inventory returns 404; insufficient stock for a new reservation returns 409;
invalid input returns 422. Quantity must be between 1 and 2147483647.

The business idempotency key is `(order_id, inventory_id)`. Repeating the request
above returns **200**, with exactly the original reservation body (including ID
and timestamps), when its quantity matches and its status is `RESERVED`. This
also works when the first request exhausted the stock. No second reservation or
stock discount is created. Reusing the key with another quantity, or when the
existing status is `RELEASED` or `CONFIRMED`, returns **409** without changes.
There is no `Idempotency-Key` HTTP header. Release, confirmation, Saga
compensations, and automatic retries are not provided by this operation.

The service owns a single database transaction: it locks inventory and attempts
an insert using PostgreSQL `ON CONFLICT DO NOTHING` on the business UNIQUE.
A conflict recovers and validates the original reservation before any stock
check. A successful insert checks stock and discounts it; insufficient stock or
any later error rolls the provisional insert and discount back together.

`ReservationService` owns the business sequence and opens the transaction through
the `InventoryUnitOfWork` contract. The SQLAlchemy unit of work supplies inventory
and reservation repositories sharing one session and handles commit and rollback;
the repositories do not commit. The API dependency composes these components.
The repository builds the shared `ReservationResponse` Pydantic model from the
inserted or retrieved entity inside the transaction, before commit. The service
returns `(ReservationResponse, created)` only after the transaction succeeds;
the API uses the internal flag to select 201 or 200 without adding JSON fields.
Response serialization requires no ORM refresh or implicit query. A validation
failure rolls back the transaction. The application deliberately depends on this
shared Pydantic model. No schema migration beyond `0002` is needed.
