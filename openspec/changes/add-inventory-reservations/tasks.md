# Tasks

Tres entregas incrementales, revisables por separado y limitadas a `services/inventory-service/`. No incorporar operaciones de negocio.

## 1. Modelo de reserva

- [x] 1.1 Añadir y exportar `InventoryReservation` con columnas, nulabilidad, constraints, defaults UTC y relación unidireccional con `Inventory` según el diseño. Verificar importación sin credenciales, configuración de mappers y DDL PostgreSQL (UUID, TIMESTAMPTZ, PK, FK, UNIQUE y CHECK); comprobar defaults invocables y ausencia de default para status; ejecutar las pruebas existentes, Ruff y formato.

## 2. Migración incremental

- [x] 2.1 Añadir revisión `0002` sobre `0001`, sin editar migraciones previas. Con los fixtures PostgreSQL existentes, añadir prueba de `0001 → head → 0001 → head` que compruebe esquema/constraints y conservación de productos e inventarios previamente persistidos; adaptar la aserción del head en las pruebas existentes y comprobar metadata sin diferencias. Documentar upgrade y rollback a `0001` en `tests/persistence/README.md`; verificar pruebas de migración, suite existente, Ruff y formato. Requiere 1.1.

## 3. Persistencia y restricciones PostgreSQL

- [x] 3.1 Añadir pruebas parametrizadas en `tests/persistence/test_inventory_reservations.py`: commit y lectura desde nueva sesión, relación con inventario, UUID y timestamps UTC, actualización ORM de `updated_at` conservando `created_at`, y existencias intactas. Cubrir los tres estados válidos; rechazo de PK duplicada, campos obligatorios nulos, status omitido o inválido, FK inexistente, cantidad cero/negativa y par pedido/inventario duplicado incluso con distinto estado; permitir cada componente repetido con otro par. Verificar causas PostgreSQL y rollback; actualizar la documentación del alcance de timestamps. Ejecutar toda la suite contra PostgreSQL, Ruff y formato mediante la imagen de desarrollo y reconstruir runtime según AGENTS.md. Requiere 2.1.
