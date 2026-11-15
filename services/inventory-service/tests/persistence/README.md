# Pruebas de persistencia

Ejecutar desde la raíz del repositorio, con `.env` preparado según el README:

```bash
docker compose up -d --wait postgres
BUILD_TARGET=development docker compose build inventory-service
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service pytest -q
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service ruff check .
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service ruff format --check .
docker compose build inventory-service
```

No se publica PostgreSQL. Las pruebas usan `Settings` y las credenciales existentes
para crear una base vacía por caso, llamada `inventory_test_<uuid>`, diferente de
la base de aplicación. El usuario local necesita permiso `CREATEDB`, que tiene el
usuario inicializado por la imagen de PostgreSQL de Compose. Cada base se elimina
al terminar el caso, después de cerrar sus conexiones. Si PostgreSQL no está
disponible, la suite falla; no se sustituye por SQLite ni se omiten los casos.

Para ejecutar solo las migraciones:

```bash
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service pytest tests/persistence/test_migrations.py -q
```

La prueba recorre `upgrade head → downgrade base → upgrade head`, compara el
esquema con la metadata y comprueba que una tabla ajena sobreviva al downgrade.

## Migraciones de la aplicación

La imagen runtime incluye Alembic y las migraciones. Con PostgreSQL disponible:

```bash
docker compose run --rm --no-deps inventory-service alembic upgrade head
docker compose run --rm --no-deps inventory-service alembic current
```

Se reutilizan las variables `POSTGRES_*` existentes. Las migraciones no se ejecutan
automáticamente al arrancar FastAPI. El rollback explícito es `alembic downgrade
base`: elimina ambas tablas y sus datos; respaldar los datos antes de usarlo.
