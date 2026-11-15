# Spec Delta

## ADDED Requirements

### Requirement: Persistencia de reservas
El almacenamiento MUST conservar reservas con `id` UUID como PK, `order_id` UUID, `inventory_id` UUID con FK a inventario, `quantity` INTEGER, `status` VARCHAR y timestamps `created_at` y `updated_at` con zona horaria. Todos los campos son obligatorios y el estado se proporciona explícitamente.

#### Scenario: Reserva confirmada y recuperada
- **WHEN** se inserta y confirma una reserva válida asociada a un inventario existente
- **THEN** otra sesión recupera sus campos, UUID y referencia al mismo inventario
- **AND** la cantidad disponible del inventario permanece intacta

#### Scenario: Campos obligatorios e integridad referencial
- **WHEN** se intenta persistir una PK duplicada, cualquier campo obligatorio nulo, un estado omitido o una referencia a inventario inexistente
- **THEN** PostgreSQL rechaza cada escritura por la restricción correspondiente

### Requirement: Restricciones de reservas
PostgreSQL MUST exigir `quantity > 0`, limitar `status` a `RESERVED`, `RELEASED` o `CONFIRMED` y garantizar UNIQUE(`order_id`, `inventory_id`) para todos los estados.

#### Scenario: Valores admitidos
- **WHEN** se persisten reservas con cantidad positiva y cada uno de los tres estados permitidos
- **THEN** las escrituras son aceptadas

#### Scenario: Valores inválidos
- **WHEN** se intenta persistir cantidad cero o negativa, o un estado diferente de los valores permitidos
- **THEN** PostgreSQL rechaza cada escritura por su CHECK correspondiente

#### Scenario: Unicidad del pedido e inventario
- **WHEN** se repite el mismo par pedido/inventario, incluso con otro estado
- **THEN** PostgreSQL rechaza el duplicado
- **AND** permite el mismo pedido con otro inventario y otro pedido con el mismo inventario

### Requirement: Timestamps de reservas
La persistencia mediante ORM MUST inicializar `created_at` y `updated_at` con instantes UTC al insertar. Una modificación efectiva mediante ORM MUST renovar `updated_at` y conservar `created_at`.

#### Scenario: Creación y modificación persistidas
- **WHEN** se inserta una reserva y posteriormente se modifica un campo en otra transacción mediante ORM
- **THEN** ambos timestamps iniciales tienen zona horaria y representan instantes UTC
- **AND** una nueva sesión observa `created_at` intacto y `updated_at` posterior al valor previo

### Requirement: Migración incremental de reservas
El esquema de reservas MUST añadirse mediante una migración posterior a la existente y poder revertirse sin perder productos, inventarios ni sus datos.

#### Scenario: Instalación sobre datos existentes y reversión
- **WHEN** una base en la revisión previa con productos e inventarios recibe la migración de reservas, se revierte a esa revisión y se vuelve a aplicar
- **THEN** se crea, elimina y recrea únicamente la tabla de reservas y sus restricciones
- **AND** los productos e inventarios previos conservan sus datos
