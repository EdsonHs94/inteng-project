# Proposal

## Why

El servicio ya dispone de conexión a PostgreSQL, pero no puede persistir productos ni existencias. Se necesita un esquema inicial con restricciones verificables antes de incorporar operaciones de negocio.

## What Changes

- Añadir modelos SQLAlchemy 2.x `Product` e `Inventory` con UUID como claves primarias.
- Persistir SKU único y nombre obligatorio; vincular inventario a producto mediante FK única y exigir cantidad disponible entera, obligatoria y no negativa.
- Incorporar una migración Alembic reversible y la configuración mínima necesaria, reutilizando la configuración de conexión existente.
- Verificar persistencia y restricciones mediante pruebas contra PostgreSQL real.

## Capabilities

### New Capabilities

- `inventory-persistence`: Almacenamiento de productos y existencias con integridad garantizada por PostgreSQL y evolución mediante migraciones.

### Modified Capabilities

Ninguna.

## Impact

Cambios limitados a modelos, configuración y migraciones Alembic, pruebas y empaquetado de las migraciones en `services/inventory-service/`. Se reutilizan las dependencias instaladas, `Settings.database_url` y PostgreSQL de Compose. Actualmente Alembic está instalado, pero no existe configuración de migraciones que reutilizar.

Fuera de alcance: endpoints, servicios y repositorios de negocio, reservas, idempotencia, control de concurrencia y cambios a otros componentes. No cambia el comportamiento de `/health`.
