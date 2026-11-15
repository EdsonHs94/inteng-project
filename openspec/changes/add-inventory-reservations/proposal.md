# Proposal

## Why

Productos y existencias ya tienen persistencia, pero falta almacenar reservas asociadas a pedidos. Incorporar su estructura e integridad permite preparar futuras operaciones de reserva sin implementar todavía comportamiento de negocio.

## What Changes

- Añadir `InventoryReservation` con UUID, pedido, inventario, cantidad, estado y timestamps UTC obligatorios, más su relación ORM con `Inventory`.
- Garantizar cantidad positiva, estado explícito entre `RESERVED`, `RELEASED` y `CONFIRMED`, y unicidad del par pedido/inventario en PostgreSQL.
- Añadir una migración Alembic incremental reversible reutilizando la configuración existente.
- Probar persistencia, relación, timestamps, restricciones y evolución del esquema sobre PostgreSQL real.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `inventory-persistence`: Añadir requisitos de almacenamiento e integridad de reservas y de su migración incremental; conservar los requisitos existentes de productos e inventario.

## Impact

Cambios previstos dentro de `services/inventory-service/`: `app/models/`, nueva revisión Alembic y pruebas/documentación en `tests/persistence/`. Se reutilizan la base declarativa, `Settings`, el entorno Alembic y los fixtures PostgreSQL existentes; no se necesitan nuevas dependencias.

Fuera de alcance: endpoints, servicios, repositorios y operaciones de negocio, idempotencia, concurrencia, transiciones de estado y modificación de cantidades disponibles. La restricción UNIQUE garantiza integridad de datos, sin implementar manejo de solicitudes repetidas.
