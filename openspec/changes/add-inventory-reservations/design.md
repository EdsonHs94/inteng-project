# Design

## Context

Ver `proposal.md` para la motivación. Existen `Base`, `Product`, `Inventory`, el entorno Alembic que registra `app.models` y la revisión `0001`. Los fixtures crean bases PostgreSQL temporales y migran a `head`; una prueba compara explícitamente la revisión actual con `0001`, por lo que deberá distinguir la revisión histórica del nuevo `head`.

## Goals / Non-Goals

**Goals:** Extender la capa de modelos y el historial de migraciones; reutilizar configuración, dependencias y aislamiento de las pruebas existentes.

**Non-Goals:** Añadir capas de negocio, transiciones de estado, sincronización de existencias, cascadas de borrado o automatización de migraciones. Aplican las exclusiones de la propuesta.

## Decisions

- **Modelo:** Crear `app/models/inventory_reservation.py` y exportarlo desde `app/models/__init__.py` para registrar su metadata. Tabla `inventory_reservations`, columnas `Mapped`/`mapped_column`, UUID nativo con `uuid4` para la PK y todos los campos NOT NULL según lo confirmado. `order_id` es una referencia externa sin FK local: no existe tabla de pedidos.
- **Integridad:** Usar FK a `inventories.id`, UNIQUE nombrado para (`order_id`, `inventory_id`) y CHECK nombrados para cantidad positiva y estados válidos. `status` será VARCHAR sin default; se prefiere CHECK frente a un ENUM nativo para respetar el tipo solicitado y simplificar la reversión. No añadir restricciones de transición ni UNIQUE parcial por estado.
- **Relación:** Incorporar `InventoryReservation.inventory` como relación ORM muchos-a-uno unidireccional. Satisface la asociación solicitada sin añadir una colección al modelo existente. No configurar cascadas de borrado; la FK conserva su comportamiento restrictivo.
- **Timestamps:** Usar `DateTime(timezone=True)` (TIMESTAMPTZ en PostgreSQL), defaults Python invocables basados en `datetime.now(UTC)` para ambos timestamps y `onupdate` equivalente para `updated_at`. Son valores calculados durante la escritura ORM, no al importar el módulo. PostgreSQL conserva el instante; las pruebas normalizan a UTC si la sesión devuelve otro offset. No añadir triggers: escrituras SQL directas deben proporcionar timestamps y no reciben mantenimiento automático de `updated_at`.
- **Migración y pruebas:** Añadir revisión `0002` con `down_revision = "0001"`, sin modificar `0001`, `env.py`, Settings ni Dockerfile. El upgrade crea la nueva tabla; el downgrade elimina solo esa tabla. Reutilizar `postgres_engine`, `migrated_engine` y `alembic_config`. Adaptar la aserción del head existente y añadir cobertura `0001 → head → 0001 → head` con datos previos, junto a persistencia y errores PostgreSQL específicos. La relación se comprueba desde una sesión nueva; las escrituras no alteran `quantity_available`.

## Risks / Trade-offs

- UNIQUE conserva el par incluso tras `RELEASED` o `CONFIRMED` → contrato explícito de integridad; reintentos y nuevas reservas del mismo par requieren un cambio futuro.
- Defaults y actualización de timestamps dependen del ORM → documentar este límite y probar tanto su mantenimiento ORM como el rechazo de NULL mediante SQL explícito.
- La referencia a pedidos carece de FK → validar únicamente UUID obligatorio; la existencia del pedido pertenece a futuras integraciones.
- El downgrade elimina reservas → probarlo solo en bases temporales y documentar su pérdida de datos, conservando las tablas anteriores.

## Migration Plan

Ejecutar `alembic upgrade head` con el flujo manual de Compose existente. Probar instalación desde cero y desde `0001` con datos, comparación con metadata y downgrade específico a `0001`; después reaplicar y ejecutar la suite, Ruff y formato. El rollback a `0001` elimina las reservas. Mantener las pruebas históricas de productos e inventario y reconstruir runtime tras las verificaciones según AGENTS.md.
