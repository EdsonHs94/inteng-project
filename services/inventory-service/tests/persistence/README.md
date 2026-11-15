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

Los casos de productos e inventario verifican commit y lectura desde otra sesión,
UUID generados por los modelos, cantidades cero y positivas y referencia nullable.
También comprueban las causas PostgreSQL de errores por claves duplicadas, SKU
duplicado, campos obligatorios nulos, producto inexistente y cantidad negativa,
con rollback después de cada operación rechazada.

## Migraciones de la aplicación

La imagen runtime incluye Alembic y las migraciones. Con PostgreSQL disponible:

```bash
docker compose run --rm --no-deps inventory-service alembic upgrade head
docker compose run --rm --no-deps inventory-service alembic current
```

Se reutilizan las variables `POSTGRES_*` existentes. Las migraciones no se ejecutan
automáticamente al arrancar FastAPI. El rollback explícito es `alembic downgrade
base`: elimina ambas tablas y sus datos; respaldar los datos antes de usarlo.

La revisión `0002` se aplica sobre `0001` con `alembic upgrade head` y agrega
reservas sin modificar productos ni inventarios. `alembic downgrade 0001` elimina
la tabla de reservas y todos sus datos, pero conserva productos e inventarios;
respaldar las reservas antes de revertir. Las pruebas ejercitan esta secuencia
con datos previos y vuelven a aplicar la revisión.

Los timestamps de reservas se generan en Python al insertar mediante el ORM;
`updated_at` se renueva al modificar mediante el ORM. SQL directo debe aportar
ambos valores y no actualiza `updated_at` automáticamente.
