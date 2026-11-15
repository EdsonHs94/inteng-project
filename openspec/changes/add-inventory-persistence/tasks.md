# Tasks

Las tareas se ejecutan en orden; cada una entrega un cambio acotado y revisable con su propia verificación. Todo el código previsto permanece dentro de `services/inventory-service/`.

## 1. Modelos

- [x] 1.1 Añadir base declarativa compartida y modelos `Product` e `Inventory` en `app/models/`, con columnas y restricciones del spec y UUID generado en Python. Verificar importación de la metadata sin credenciales y compilación del DDL para PostgreSQL, incluyendo tipos, nulabilidad, PK, UNIQUE, FK y CHECK; ejecutar Ruff y formato sobre los archivos incorporados. No añadir endpoints ni capas de negocio.

## 2. Migración inicial

- [x] 2.1 Configurar Alembic reutilizando `Settings.database_url`, registrar la metadata y añadir revisión inicial reversible; copiar los artefactos de Alembic en las etapas existentes del Dockerfile. Añadir fixture para una base PostgreSQL de pruebas dedicada y prueba de `upgrade head → downgrade base → upgrade head` que compruebe tablas y restricciones, rechazando la base de aplicación como destino destructivo. Documentar preparación y comandos en `tests/persistence/README.md`; verificar la prueba mediante la imagen de desarrollo en Compose y ejecutar Ruff y formato. Requiere 1.1.

## 3. Persistencia y restricciones

- [x] 3.1 Reutilizar el fixture PostgreSQL para probar commit y lectura desde otra sesión de productos e inventarios (cantidad cero y positiva), rechazo de PK duplicadas, SKU duplicado o nulo, nombre nulo, FK inexistente, producto repetido y cantidad negativa o nula; comprobar también la referencia nullable. Parametrizar casos con rollback y verificar la causa de cada `IntegrityError`. Ejecutar la suite completa en la imagen de desarrollo con PostgreSQL disponible, `ruff check .` y `ruff format --check .`; reconstruir runtime conforme a AGENTS.md. Requiere 2.1.
