# Proposal

## Why

Actualmente todo duplicado de `POST /reservations` devuelve 409, incluso cuando el cliente repite una solicitud cuyo resultado perdió. Se necesita recuperar la reserva original sin otro descuento de stock y distinguir un reintento válido de una petición incompatible.

## What Changes

- Usar el par existente (`order_id`, `inventory_id`) como clave de idempotencia de negocio.
- Mantener 201 para creación y devolver 200 con la reserva existente si cantidad y estado `RESERVED` coinciden, incluso con stock disponible en cero.
- Mantener 409 para cantidad distinta, estado diferente de `RESERVED` o stock insuficiente al crear una reserva nueva.
- Resolver la unicidad mediante PostgreSQL conservando la transacción y el bloqueo de inventario existentes.
- **BREAKING**: Los duplicados idénticos dejan de responder 409; actualizar contratos, documentación y pruebas previas.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `stock-reservation`: Incorporar reintentos idempotentes y ajustar conflictos y respuestas ante solicitudes simultáneas del mismo par.

## Impact

Cambios dentro de `services/inventory-service/`: contratos y repositorio de reservas, `ReservationService`, integración con el Unit of Work, router, pruebas y documentación. Se conserva `ReservationResponse` como modelo Pydantic compartido y el formato JSON existente. No se requieren tablas, modelos ni migraciones nuevas; `inventory-persistence` conserva sus constraints.

Fuera de alcance: cabecera `Idempotency-Key`, nuevas tablas, release/confirm, compensaciones Saga y pruebas intensivas de concurrencia. Se mantienen y adaptan las comprobaciones concurrentes acotadas existentes.
