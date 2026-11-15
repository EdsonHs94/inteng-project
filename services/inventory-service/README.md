# Inventory service

Apply the existing Alembic migrations through `0002` before using reservations.

```http
POST /reservations HTTP/1.1
Content-Type: application/json

{"order_id":"6dcf531e-df12-457a-9d2c-e54b3b933174","inventory_id":"104a9f12-736e-4ec2-842e-1abb5bc9c663","quantity":3}
```

A successful request returns 201 with the reservation ID, order ID, inventory ID,
quantity, `RESERVED` status, and creation and update timestamps. A missing
inventory returns 404; insufficient stock or an existing order/inventory pair
returns 409; invalid input returns 422. Quantity must be between 1 and 2147483647.
The service owns a single database transaction: it locks inventory, checks the
pair and stock, and commits the discount and reservation together. A failed
transaction rolls both back. Repeating a request is not idempotent: the same pair
returns 409, including when the existing reservation has another status. Release,
confirmation, and automatic retries are not provided by this operation.

`ReservationService` owns the business sequence and opens the transaction through
the `InventoryUnitOfWork` contract. The SQLAlchemy unit of work supplies inventory
and reservation repositories sharing one session and handles commit and rollback;
the repositories do not commit. The API dependency composes these components.
The repository builds the shared `ReservationResponse` Pydantic model from the
flushed ORM entity inside the transaction, before commit. The service returns
that model only after commit succeeds; response serialization requires no ORM
refresh or implicit query. A validation failure rolls back both writes. The
application deliberately depends on this shared Pydantic model.
