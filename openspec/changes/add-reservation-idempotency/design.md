# Design

## Context

Ver `proposal.md` para la motivación. `ReservationService` ya usa contratos y `InventoryUnitOfWork`; los repositorios son clases y la API compone dependencias con `Depends`. Hoy se bloquea inventario, se consulta `has_reservation`, se descuenta stock y se inserta; todo duplicado produce 409. La UNIQUE nombrada `uq_inventory_reservations_order_inventory` es inmediata. El router devuelve `ReservationResponse` con 201 fijo. Existen pruebas de rollback, serialización sin SQL y dos solicitudes simultáneas; una prueba modifica artificialmente la UNIQUE a DEFERRABLE.

## Goals / Non-Goals

**Goals:** Resolver creación/reintento con la clave existente, sin alterar cantidades ni timestamps al recuperar, manteniendo clases, contratos y una transacción PostgreSQL.

**Non-Goals:** Nuevos DTO/View, cambios de esquema, cabeceras de idempotencia, locks en memoria, reintentos ilimitados, transiciones de reservas o pruebas intensivas. No convertir errores ajenos a la clave de negocio en éxitos.

## Decisions

- **Arbitraje PostgreSQL:** Extender el repositorio con `try_create_reservation(...) -> ReservationResponse | None` mediante `INSERT ... ON CONFLICT ON CONSTRAINT uq_inventory_reservations_order_inventory DO NOTHING RETURNING ...` y `get_by_pair(...) -> ReservationResponse | None`. Solo el conflicto de esa UNIQUE devuelve ausencia de inserción; PK, FK, CHECK, validación y otros errores conservan su fallo/rollback. Reutilizar los defaults UUID/UTC existentes al insertar y comprobarlos en integración. `DO NOTHING` evita modificar incluso `updated_at`; no usar UPSERT con UPDATE.
- **Transacción y orden:** Mantener `with uow.begin()` y `SELECT FOR UPDATE` del inventario como primer acceso. Si falta inventario, 404. Intentar insertar la reserva `RESERVED` antes de comprobar suficiencia: si se insertó, verificar stock y descontar; ante insuficiencia, lanzar error y revertir también la inserción. Si hubo conflicto, recuperar la reserva por su par en una sentencia posterior bajo READ COMMITTED; resolver cantidad/estado y devolverla sin comprobar suficiencia ni escribir stock. El bloqueo dura hasta commit/rollback y se conserva también para las solicitudes del mismo inventario.
- **Reintento:** Cantidad igual y estado `RESERVED` permiten recuperar; cualquier otra combinación genera un conflicto de aplicación y HTTP 409. La búsqueda no altera timestamps ni reconstruye una reserva nueva. Si un conflicto no permite recuperar su fila, fallar sin devolver un éxito inventado. El servicio no conoce SQLAlchemy, SQLSTATE ni el nombre del constraint: estos detalles siguen en persistencia.
- **Resultado y HTTP:** Mantener `ReservationResponse` como único modelo Pydantic compartido. El servicio devuelve `(reservation, created)` con bandera booleana interna; no añadir campos al JSON ni otra clase DTO. La ruta selecciona HTTP 201 o 200 con `Response` después de completar la transacción, y documenta ambas respuestas en OpenAPI. Los errores de cantidad/estado se mapean a 409; 404, 422 y fallos inesperados conservan su semántica.
- **Alternativas:** SELECT previo sin protección no arbitra unicidad y se descarta. Capturar una UniqueViolation y recuperar tras rollback completo también sería seguro, pero añade una segunda transacción y una ruta de recuperación más compleja. Se elige ON CONFLICT dirigido al constraint real y se mantiene el bloqueo de fila ya utilizado, sin introducir infraestructura adicional.
- **Pruebas:** Mantener fixtures de PostgreSQL y la implementación en memoria de contratos. Verificar creación 201, replay 200 con cuerpo idéntico y stock cero, cantidad distinta, estados RELEASED/CONFIRMED, una sola fila/descuento y timestamps intactos. Adaptar las pruebas concurrentes existentes: mismo par/cantidad pasa de 201/409 a 201/200; pedidos diferentes siguen 201/409 con última unidad. Actualizar puntos de fallo al nuevo orden insertar/descontar para conservar prueba de rollback de ambas escrituras. Las pruebas del repositorio deben ejercer un conflicto real, no simularlo como éxito.

## Risks / Trade-offs

- ON CONFLICT requiere la UNIQUE inmediata existente → no modificarla a DEFERRABLE; adaptar el test que fabrica ese esquema y conservar cobertura de fallo al commit/rollback mediante un mecanismo compatible con el esquema soportado.
- Inserción antes de comprobar stock produce una fila provisional → permanece dentro de la misma transacción y se revierte si falta stock o falla cualquier paso; comprobar desde otra sesión.
- Un reintento puede esperar el bloqueo del inventario → se conserva la protección actual; estrés y optimización quedan para el siguiente change.
- El orden de escrituras cambia → no debilitar pruebas de fallo posterior al descuento, commit y validación Pydantic; actualizar su instrumentación al contrato nuevo.
- Una reserva de otro estado no es reutilizable → devolver 409 sin reactivación ni compensación automática.

## Migration Plan

No hay migración: se requiere el esquema actual en `0002`. Actualizar clientes/documentación para admitir 200 además de 201 y sustituir las expectativas previas de duplicado idéntico 409. Verificar suite completa sobre PostgreSQL, Ruff y formato con el flujo Docker de AGENTS.md; reconstruir runtime al terminar. Un rollback de código conserva datos, pero vuelve a rechazar los reintentos con 409.
