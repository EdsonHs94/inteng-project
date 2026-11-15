# inventory-persistence Specification

## Purpose

Persistir productos y existencias en PostgreSQL con integridad de datos verificable y un esquema gestionado por migraciones reversibles.

## Requirements

### Requirement: Persistencia de productos
El almacenamiento MUST conservar productos con `id` UUID como clave primaria, `sku` VARCHAR único y no nulo, y `name` VARCHAR no nulo.

#### Scenario: Producto confirmado y recuperado
- **WHEN** se inserta y confirma un producto válido
- **THEN** otra sesión recupera el mismo UUID, SKU y nombre

#### Scenario: Restricciones de producto
- **WHEN** se intenta insertar un UUID primario duplicado, un SKU duplicado, un SKU nulo o un nombre nulo
- **THEN** PostgreSQL rechaza cada operación por la restricción correspondiente

### Requirement: Persistencia e integridad de inventario
El almacenamiento MUST conservar inventarios con `id` UUID como clave primaria, `product_id` UUID con FK a producto y unicidad, y `quantity_available` INTEGER no nulo con CHECK >= 0. `product_id` admite NULL conforme al esquema solicitado.

#### Scenario: Existencias válidas
- **WHEN** se confirma inventario de un producto existente con cantidad cero o positiva
- **THEN** otra sesión recupera el mismo UUID, producto y cantidad

#### Scenario: Restricciones de inventario
- **WHEN** se intenta insertar un UUID primario duplicado, un producto inexistente, un segundo inventario para el mismo producto, una cantidad negativa o una cantidad nula
- **THEN** PostgreSQL rechaza cada operación por la restricción correspondiente

#### Scenario: Referencia opcional
- **WHEN** se confirma un inventario con `product_id` nulo y cantidad válida
- **THEN** PostgreSQL acepta el registro

### Requirement: Evolución reversible del esquema
El esquema MUST poder instalarse mediante una migración sobre una base vacía y revertirse eliminando solo las tablas incorporadas por este cambio.

#### Scenario: Instalación y reversión
- **WHEN** se aplica la migración inicial, se revierte y se vuelve a aplicar en una base de pruebas vacía
- **THEN** se crean, eliminan y recrean las tablas y sus restricciones correctamente
