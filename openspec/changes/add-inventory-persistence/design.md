# Design

## Context

Ver `proposal.md` para la motivación. El servicio usa sesiones SQLAlchemy síncronas con psycopg y `Settings.database_url`. `app/models/` está vacío; no existe base declarativa, `alembic.ini` ni entorno Alembic. Las pruebas actuales de health usan SQLite. El Dockerfile solo copia `app/` y, en desarrollo, `tests/`.

## Goals / Non-Goals

**Goals:** Mantener entidades en la capa de modelos, configurar migraciones con las credenciales existentes y verificar las restricciones en PostgreSQL real.

**Non-Goals:** Añadir capas o patrones de negocio, crear tablas al iniciar FastAPI, ejecutar migraciones automáticamente, modificar Compose o cambiar health. Aplican las exclusiones de la propuesta.

## Decisions

- **Modelos:** Añadir `app/models/base.py`, `product.py` e `inventory.py`, con una única `DeclarativeBase`, `Mapped` y `mapped_column`. Usar tablas `products` e `inventories`, UUID nativo y generación Python `uuid4` para los identificadores. Mantener esta base independiente del engine para que importar metadata no requiera credenciales. Alternativa descartada: ubicar entidades en repositorios o acoplarlas al arranque de FastAPI.
- **Columnas y restricciones:** `sku` y `name` usan VARCHAR sin límite adicional; no se agregan normalización, validación de cadena vacía ni unicidad insensible a mayúsculas. `product_id` es nullable según el alcance literal, con FK a `products.id` y UNIQUE. `quantity_available` es INTEGER NOT NULL sin valor por defecto, con CHECK nombrado `quantity_available >= 0`. No se agregan cascadas, relaciones ORM ni creación automática de inventario. PK, FK, UNIQUE, NOT NULL y CHECK quedan garantizados por la base, frente a validaciones solo en Python.
- **Alembic:** Crear `alembic.ini`, `alembic/env.py`, plantilla y una revisión inicial dentro del servicio. Reutilizar `Settings.database_url` directamente al configurar la conexión; no duplicar credenciales ni renderizarlas en archivos. Importar ambos modelos para registrar `target_metadata`. La revisión crea primero productos y luego inventarios; el downgrade invierte ese orden. Añadir únicamente las copias necesarias al Dockerfile para disponer de las migraciones en las imágenes existentes. Se elige Alembic frente a `create_all` para mantener un historial reversible.
- **Pruebas:** Añadir pruebas en `tests/persistence/`, sin modificar las pruebas de health. Ejecutarlas mediante la imagen de desarrollo en la red existente de Compose, sin publicar PostgreSQL. Usar una base de pruebas dedicada, distinta de la base de aplicación; permitir crearla previamente o con un fixture usando las credenciales locales y validar el destino antes de operaciones destructivas. Aplicar las migraciones reales, confirmar registros y leerlos desde otra sesión. Cada caso de restricción verifica `IntegrityError` y su causa PostgreSQL, con rollback entre casos. SQLite no valida este contrato.

## Risks / Trade-offs

- Alembic carece de configuración previa → añadir el mínimo entorno y reutilizar únicamente la configuración de conexión existente; no refactorizarla.
- `product_id` nullable permite inventario sin producto → conservar el esquema solicitado; exigir referencia obligatoria sería un cambio posterior del contrato.
- Pruebas de migraciones eliminan tablas → limitar upgrade/downgrade a la base de pruebas dedicada y rechazar el destino de aplicación.
- El downgrade elimina los datos de ambas tablas → reservarlo para rollback explícito y pruebas; respaldar datos antes de usarlo en una base con información.
- Tres tareas incrementales tienen dependencias de orden → cada una entrega un cambio acotado, comprobable y revisable por separado; migraciones se apoyan en modelos y pruebas se apoyan en migraciones.

## Migration Plan

Desde la carpeta del servicio, comprobar importación de modelos y construir la imagen de desarrollo. Con PostgreSQL listo y usando la configuración existente, ejecutar `alembic upgrade head` en un contenedor de Compose. Verificar en la base dedicada `upgrade head → downgrade base → upgrade head` y las restricciones. Ejecutar pytest, Ruff y comprobación de formato; reconstruir la imagen runtime según las instrucciones del repositorio. No añadir migraciones al arranque del API. Para revertir explícitamente el esquema, usar `alembic downgrade base`, que elimina primero inventarios y luego productos.
