# stock-reservation Specification

## Purpose

Permitir reservar stock mediante HTTP con creación de reserva y descuento atómicos, rechazando conflictos sin consumir existencias adicionales.

## Requirements

### Requirement: Creación HTTP de reserva
El servicio MUST aceptar `POST /reservations` con `order_id` UUID, `inventory_id` UUID y `quantity` entera positiva. Con inventario existente, stock suficiente y par pedido/inventario libre, MUST responder 201 con `id`, `order_id`, `inventory_id`, `quantity`, `status` igual a `RESERVED`, `created_at` y `updated_at`.

#### Scenario: Reserva exitosa
- **WHEN** se solicitan 3 unidades de un inventario con 5 disponibles y sin reserva para ese pedido
- **THEN** la respuesta es 201 con la reserva creada y timestamps con zona horaria
- **AND** una sesión independiente observa esa reserva y 2 unidades disponibles

#### Scenario: Consumo exacto del stock
- **WHEN** la cantidad solicitada coincide con el stock disponible
- **THEN** la operación responde 201 y deja el stock en cero

### Requirement: Validación de solicitud
La API MUST responder 422 sin escrituras ante campos requeridos ausentes, UUID inválidos o quantity que no valide como entero entre 1 y 2147483647, rango positivo del INTEGER persistido.

#### Scenario: Solicitud inválida
- **WHEN** falta un campo requerido, un identificador no es UUID o quantity es nula, no entera, cero, negativa o superior al rango admitido
- **THEN** la respuesta es 422 y no cambian inventarios ni reservas

### Requirement: Inventario inexistente
La operación MUST responder 404 sin crear reservas si el identificador de inventario no existe.

#### Scenario: Identificador desconocido
- **WHEN** se solicita una reserva con inventory_id válido pero inexistente
- **THEN** la respuesta es 404 y no se persiste ninguna reserva

### Requirement: Conflictos de reserva
La operación MUST responder 409 sin nuevas escrituras si una reserva nueva no tiene stock suficiente o si la misma clave de negocio ya existe con cantidad distinta o estado diferente de `RESERVED`. La clave existente MUST resolverse antes de evaluar stock para una creación nueva y nunca reactivarse.

#### Scenario: Stock insuficiente
- **WHEN** se solicitan más unidades de las disponibles para una clave nueva, incluido inventario con stock cero
- **THEN** la respuesta es 409 y stock y reservas permanecen intactos

#### Scenario: Reserva duplicada
- **WHEN** se repite un par pedido/inventario previamente reservado con otra cantidad
- **THEN** la respuesta es 409 y no se crea otra reserva ni se vuelve a descontar stock, aun si el inventario está agotado

#### Scenario: Reserva en otro estado
- **WHEN** existe una reserva del mismo par en estado `RELEASED` o `CONFIRMED`, con igual o distinta cantidad
- **THEN** la respuesta es 409, la reserva no se reactiva y no se modifica stock ni timestamps

### Requirement: Atomicidad de reserva y stock
La creación de reserva y el descuento MUST confirmarse en una única transacción. Ante cualquier fallo de esa transacción, ambas escrituras MUST revertirse por completo. Los errores inesperados MUST producir una respuesta de servidor fallida sin exponer detalles de PostgreSQL.

#### Scenario: Error después del descuento
- **WHEN** falla la creación o confirmación de una reserva después de escribir el descuento
- **THEN** otra sesión observa el stock original y ninguna reserva nueva
- **AND** no se devuelve HTTP 201

### Requirement: Stock consistente ante solicitudes simultáneas
Las solicitudes concurrentes MUST respetar la disponibilidad actualizada sin producir stock negativo ni descuentos por reservas rechazadas o recuperadas, manteniendo una única reserva por par pedido/inventario.

#### Scenario: Dos pedidos compiten por stock limitado
- **WHEN** dos solicitudes de pedidos diferentes compiten por la última unidad del mismo inventario
- **THEN** una responde 201 y la otra 409
- **AND** queda una reserva nueva y stock cero

#### Scenario: Dos solicitudes del mismo par
- **WHEN** dos solicitudes simultáneas repiten el mismo pedido/inventario y cantidad con stock suficiente para una reserva
- **THEN** una responde 201 y la otra 200 con la misma reserva
- **AND** se persiste una reserva y se descuenta su cantidad una sola vez

### Requirement: Reintentos idempotentes por clave de negocio
El par (`order_id`, `inventory_id`) MUST identificar una reserva única. Una solicitud válida posterior con la misma clave, igual cantidad y reserva en estado `RESERVED` MUST devolver HTTP 200 con la reserva original, conservando todos sus campos y el inventario sin escrituras adicionales.

#### Scenario: Reintento idéntico
- **WHEN** se repite una reserva creada previamente con igual clave y cantidad
- **THEN** la primera respuesta es 201 y la posterior es 200 con el mismo id, cantidad, estado y timestamps
- **AND** una sesión independiente observa una sola reserva y un único descuento de stock

#### Scenario: Reintento con stock agotado
- **WHEN** una reserva dejó el stock en cero o por debajo de la cantidad solicitada y se repite idénticamente
- **THEN** se devuelve 200 con la reserva original sin volver a evaluar suficiencia para crearla ni descontar stock
