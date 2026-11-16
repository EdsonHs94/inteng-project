# Tasks

Tres entregas acotadas, independientes para revisión y con verificación propia. Se ejecutan en orden porque servicio/API consumen los contratos del repositorio. Todo el código queda dentro de `services/inventory-service/`.

## 1. Repositorio y contratos

- [x] 1.1 Extender el contrato y `SqlAlchemyReservationRepository` con inserción condicional dirigida a la UNIQUE existente y lectura de la reserva por par, devolviendo `ReservationResponse` y distinguiendo conflicto sin inserción. Conservar temporalmente las operaciones usadas por el servicio actual para que esta entrega sea verificable por separado. Añadir pruebas PostgreSQL de inserción/defaults, conflicto real sin sobrescritura de timestamps, recuperación del registro original y rollback; comprobar que errores de otros constraints no se absorben. Ejecutar pruebas de repositorio, suite existente, Ruff y formato.

## 2. Servicio y respuesta HTTP

- [x] 2.1 Integrar los nuevos contratos en `ReservationService` y el Unit of Work: bloquear inventario, intentar creación y resolver reserva existente antes de comprobar stock; recuperar solo si cantidad coincide y estado es RESERVED, con `(ReservationResponse, created)` sin otro DTO. Mapear creación a 201, replay a 200 y cantidad/estado incompatible a 409; documentar ambas respuestas en OpenAPI. Añadir pruebas en memoria y HTTP básicas, actualizar las expectativas anteriores de duplicado idéntico y retirar métodos obsoletos. Adaptar instrumentación de rollback/commit al nuevo orden sin modificar constraints productivos ni convertir errores ajenos en duplicados. Ejecutar pruebas del servicio/API, suite existente, Ruff y formato. Requiere 1.1.

## 3. Regresiones de idempotencia

- [x] 3.1 Ampliar pruebas PostgreSQL/HTTP para reintentos sucesivos idénticos, stock cero o menor a quantity, cantidad distinta y estados RELEASED/CONFIRMED con igual/distinta cantidad. Verificar cuerpo original, timestamps intactos, una sola reserva y un único descuento desde otra sesión, además de rollback de inserción y descuento ante error. Conservar las dos pruebas concurrentes acotadas existentes con resultados 201/200 para mismo par/cantidad y 201/409 para pedidos distintos por última unidad; no añadir carga intensiva. Documentar clave de negocio, ejemplos 201/200/409 y límites; ejecutar suite completa PostgreSQL, Ruff y formato en Docker y reconstruir runtime según AGENTS.md. Requiere 2.1.

Verificación de esta ejecución: por instrucción explícita del usuario se ejecutan únicamente los tests relacionados con reservas, no la suite completa. No se crean commits.

Resultado: 43 tests relacionados aprobados sobre PostgreSQL y en memoria; Ruff y formato de los 8 archivos Python modificados correctos; validación estricta OpenSpec y configuración Compose correctas; imagen runtime reconstruida. Revisión independiente sin hallazgos.
