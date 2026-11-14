# Inventory monorepo

Monorepo de APIs en FastAPI. Cada servicio tendrá su propia carpeta en `services/`,
sus dependencias y su Dockerfile. El primer servicio es `inventory-service`.

## Estructura

```text
services/inventory-service/
├── app/
│   ├── main.py         # Aplicación y ciclo de vida
│   ├── api/routes/     # Endpoints HTTP
│   ├── core/           # Configuración y conexión a PostgreSQL
│   ├── schemas/        # Objetos Pydantic de entrada y salida
│   ├── services/       # Lógica de negocio (pendiente)
│   ├── repositories/   # Acceso a datos (pendiente)
│   └── models/         # Modelos SQLAlchemy (pendiente)
├── tests/
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

El flujo de negocio será rutas → servicios → repositorios. Health consulta la base
directamente porque todavía no existe lógica de negocio. Alembic está instalado;
su configuración y las migraciones se añadirán con el primer modelo. Saga,
mensajería y los demás servicios quedan para etapas posteriores.

## Ejecutar con Docker

Requisitos: Docker Engine y Docker Compose v2. No hace falta instalar Python ni uv
localmente para ejecutar el API o las pruebas.

```bash
cp .env.example .env  # Solo la primera vez; ajustar las credenciales locales

docker compose config --quiet
docker compose up --build -d
curl -i http://localhost:8000/health
```

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Health: `200 {"status":"ok","database":"ok"}` si `SELECT 1` funciona;
  `503 {"status":"error","database":"unavailable"}` si falla PostgreSQL.

El API espera que PostgreSQL esté listo. PostgreSQL solo es accesible dentro de la
red de Docker y conserva los datos en un volumen. `.env` no se versiona; las
credenciales de ejemplo son exclusivamente para desarrollo local.

```bash
docker compose logs -f inventory-service
docker compose down
```

`down` conserva el volumen. Cambiar las credenciales en `.env` no modifica los
usuarios de una base ya inicializada. Después de cambiar código, reconstruir con
`docker compose up --build -d`.

## Pruebas y estilo

La imagen `runtime` excluye las herramientas de desarrollo. Construir la etapa de
desarrollo antes de ejecutar los controles:

```bash
BUILD_TARGET=development docker compose build inventory-service
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service pytest -q
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service ruff check .
BUILD_TARGET=development docker compose run --rm --no-deps inventory-service ruff format --check .
```

Las pruebas sustituyen la sesión PostgreSQL por SQLite y no requieren la base
activa. Para volver a la imagen de ejecución:

```bash
docker compose up --build -d
```

Para comprobar la dependencia real, detener PostgreSQL, consultar health y volver
a arrancarlo:

```bash
docker compose stop postgres
curl -i http://localhost:8000/health  # 503

docker compose start postgres
# Una vez listo PostgreSQL:
curl -i http://localhost:8000/health  # 200
```

Las dependencias se declaran por servicio y las versiones resueltas se guardan en
`uv.lock`. Al modificarlas, regenerar el lock con uv desde la carpeta del servicio
y reconstruir la imagen. Ruff usa cuatro espacios y un máximo de 88 caracteres.
