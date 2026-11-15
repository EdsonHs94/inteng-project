# Proposal

## Why

El servicio ya almacena inventarios y reservas, pero todavía no ofrece una operación para reservar stock. Se necesita coordinar ambas escrituras con integridad transaccional antes de añadir reintentos idempotentes o flujos de liberación y confirmación.

## What Changes

- Incorporar `POST /reservations` con request/response Pydantic y respuesta 201 con la reserva creada en estado `RESERVED`.
- Añadir servicio transaccional y repositorios para verificar inventario, detectar duplicados, comprobar disponibilidad, descontar stock y persistir la reserva.
- Responder 404 para inventario inexistente, 409 para stock insuficiente o reserva existente, y 422 para solicitudes inválidas.
- Garantizar commit conjunto o rollback completo, evitando stock negativo ante solicitudes simultáneas.
- Verificar los casos HTTP y de negocio sobre PostgreSQL real, incluyendo rollback y una comprobación concurrente acotada.

## Capabilities

### New Capabilities

- `stock-reservation`: Creación HTTP de reservas con descuento de stock atómico, conflictos y consistencia ante solicitudes simultáneas.

### Modified Capabilities

Ninguna. Se reutilizan los contratos de `inventory-persistence`: el descuento pertenece a la nueva operación de negocio, no a insertar directamente un modelo de reserva.

## Impact

Cambios limitados a `services/inventory-service/`: router y schemas de reservas, servicio, repositorios, registro del router, pruebas y documentación. Se reutilizan sesiones, modelos, migraciones, constraints y fixtures PostgreSQL existentes; no se prevén nuevas dependencias ni cambios de esquema.

Fuera de alcance: idempotencia funcional de reintentos (change 004), pruebas de concurrencia intensivas (change 005), release/confirm, Temporal, Celery y Saga. Repetir una reserva devuelve 409; no devuelve la respuesta previa como éxito.
