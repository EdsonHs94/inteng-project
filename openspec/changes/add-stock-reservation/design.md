# Design

## Context

Ver `proposal.md` para la motivación. Solo existe el router de health; `app/services/` y `app/repositories/` están vacíos. `get_session` entrega una sesión síncrona sin commit automático. Existen `Inventory`, `InventoryReservation`, la FK y los CHECK, más `uq_inventory_reservations_order_inventory`. Las pruebas actuales ya disponen de PostgreSQL temporal por caso y HTTPX ASGITransport.

## Goals / Non-Goals

**Goals:** Primer flujo rutas → servicio → repositorios, con una única transacción, errores HTTP definidos y protección de stock desde esta operación.

**Non-Goals:** Cambiar modelos o migraciones, introducir un framework de unidad de trabajo, reintentos automáticos, idempotencia funcional, nuevas transiciones de reservas o pruebas de carga. No alterar la semántica de persistencia directa: insertar un modelo no dispara descuentos.

## Decisions

- **API:** Añadir `app/api/routes/reservations.py` y registrarlo en `app/main.py`. Handler síncrono con `get_session`; solo valida/delega y traduce errores del servicio. `app/schemas/reservation.py` define request con UUID y `quantity: int` acotada a 1..2147483647, y response con los ocho campos públicos del spec. Usar validación Pydantic estándar y errores 422; no aceptar estado aportado por el cliente como estado de la reserva. HTTP 201 se devuelve después del commit.
- **Servicio y repositorios:** `app/services/reservation.py` coordina la operación y define errores de negocio independientes de HTTP. `app/repositories/inventory.py` contiene lectura con bloqueo y escritura de cantidad; `app/repositories/inventory_reservation.py` consulta el par y añade la reserva. Los repositorios reciben la misma sesión, realizan SQL/ORM y pueden hacer flush, pero nunca commit ni rollback. El servicio calcula el nuevo stock y fija `status="RESERVED"`; ni rutas ni schemas acceden a PostgreSQL.
- **Transacción:** El servicio abre `with session.begin()` sobre la sesión nueva, antes de cualquier consulta. Secuencia: bloquear inventario → 404 si falta → comprobar duplicado → comprobar stock → persistir descuento → insertar reserva y hacer flush → construir resultado con los valores generados → commit al salir. Ante excepción el contexto revierte todo, también el descuento ya enviado a PostgreSQL. Devolver un resultado inmutable con campos escalares para mapearlo al schema en la ruta, sin refresh ni lazy loading después del commit y sin acoplar el servicio a Pydantic.
- **Concurrencia:** Elegir `SELECT ... FOR UPDATE` en la fila de inventario, mantenido hasta commit/rollback. PostgreSQL serializa las decisiones sobre el mismo inventario, evitando leer disponibilidad obsoleta. Alternativa válida pero descartada aquí: UPDATE condicional con RETURNING, que exige consultas adicionales para distinguir ausencia, stock y duplicados. Leer/modificar sin bloqueo se descarta porque puede perder actualizaciones. Cada operación afecta un solo inventario; no se añaden bloqueos globales ni nivel SERIALIZABLE.
- **Errores y constraints:** Inventario inexistente se comprueba primero; luego duplicado de cualquier estado y stock insuficiente generan conflictos distintos del servicio, ambos HTTP 409. La UNIQUE existente es la defensa final. Traducir únicamente SQLSTATE 23505 con nombre `uq_inventory_reservations_order_inventory`, una vez completado el rollback; no convertir cualquier `IntegrityError` en duplicado. CHECK, FK y NOT NULL siguen activos. Los demás errores se propagan como 500 genérico tras rollback; la ruta no expone SQL ni detalles de conexión. El servicio también rechaza cantidades no positivas antes de mutar datos.
- **Pruebas:** Reutilizar fixtures PostgreSQL mediante un módulo compartido de tests si es necesario para `tests/api/`, sin duplicar su configuración. Overrides de `get_session` entregan una sesión nueva de la base temporal por petición y se limpian al terminar. Probar repositorios y servicio con PostgreSQL real; probar el contrato HTTP con ASGITransport y comprobar estado final desde otra sesión. Para rollback, provocar un fallo controlado después de un descuento efectivamente escrito; no añadir interruptores de fallo al código productivo. Dos pruebas concurrentes acotadas usan conexiones/sesiones independientes y coordinación explícita con timeout, sin esperas arbitrarias ni carga intensiva.

## Risks / Trade-offs

- Bloqueo por inventario reduce paralelismo en un artículo muy solicitado → transacción breve, sin llamadas externas ni trabajo ajeno dentro del bloqueo; pruebas de carga quedan en change 005.
- Un reintento tras respuesta perdida devuelve 409 → comportamiento explícito; resolución idempotente queda en change 004.
- Escritores externos que eludan este servicio no coordinan descuento y reserva → los constraints protegen integridad local; el contrato transaccional corresponde a esta operación.
- Flush o commit fallido puede dejar la sesión inválida → rollback antes de clasificar el error y sesión por petición; comprobar stock y reserva desde otra sesión en los tests.

## Migration Plan

No hay migración nueva. Requiere tener aplicado el esquema actual hasta `0002`. Construir la imagen de desarrollo, ejecutar pruebas sobre PostgreSQL, Ruff y formato, y reconstruir runtime conforme a AGENTS.md. Documentar un ejemplo de `POST /reservations` en la documentación del servicio. Revertir el código del endpoint conserva el esquema y los datos existentes.
