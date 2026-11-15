# Tasks

Tres entregas incrementales y revisables por separado, limitadas a `services/inventory-service/`.

## 1. Repositorios

- [x] 1.1 Añadir repositorios para leer/bloquear inventario, persistir cantidad disponible, consultar reservas por par e insertar reservas con flush sin commit/rollback. Compartir los fixtures PostgreSQL existentes con las nuevas pruebas si hace falta. Verificar con pruebas reales lectura, ausencia, escritura, detección de duplicados y rollback controlado por el llamador; ejecutar suite existente, Ruff y formato.

## 2. Servicio transaccional

- [x] 2.1 Implementar servicio con una sesión/transacción, errores de negocio y resultado inmutable: bloquear inventario, validar existencia/duplicado/stock, descontar, crear RESERVED y confirmar; clasificar únicamente la UNIQUE esperada después del rollback. Añadir pruebas PostgreSQL de éxito, stock exacto e insuficiente, inventario inexistente, duplicado sin nuevo descuento y fallo controlado después de un descuento escrito, verificando estado desde otra sesión. Documentar la responsabilidad transaccional y ejecutar pruebas del servicio, suite existente, Ruff y formato. Requiere 1.1.

## 3. Endpoint e integración

- [x] 3.1 Añadir schemas Pydantic y `POST /reservations`, registrar router y mapear errores a 404/409 con éxito 201 y validación 422. Probar con HTTPX/ASGITransport y PostgreSQL los contratos de respuesta, datos inválidos, ausencia, stock insuficiente, duplicado, rollback y error inesperado sin detalles SQL. Añadir dos pruebas simultáneas acotadas con sesiones independientes: dos pedidos por la última unidad y dos solicitudes del mismo par; comprobar resultados 201/409 y stock final. Documentar ejemplo HTTP, respuestas, requisito de esquema `0002` y ausencia de idempotencia; ejecutar toda la suite contra PostgreSQL, Ruff y formato en la imagen de desarrollo y reconstruir runtime según AGENTS.md. Requiere 2.1.
