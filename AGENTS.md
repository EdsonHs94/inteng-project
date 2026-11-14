# Repository Guidelines

## Project Structure & Module Organization

This monorepo keeps independently deployable APIs under `services/`. Only
`services/inventory-service/` currently exists. Each future service should own its
Dockerfile, dependency manifest, lockfile, and tests. Root files contain shared
Compose configuration, environment examples, and documentation.

Inside Inventory, `app/api/routes/` defines HTTP endpoints; `schemas/` contains
Pydantic objects; `core/` owns settings and database connections. Reserve
`services/` for business logic, `repositories/` for persistence operations, and
`models/` for SQLAlchemy entities. Business requests should flow from routes to
services to repositories. Tests live in the service's `tests/` directory.

## Build, Test, and Development Commands

Copy `.env.example` to `.env` once and adjust local credentials.

- `docker compose config --quiet`: validate configuration.
- `docker compose up --build -d`: build and start the API and PostgreSQL.
- `curl -i http://localhost:8000/health`: verify database readiness through the API.
- `docker compose down`: stop the stack while retaining database data.

For development checks, first run
`BUILD_TARGET=development docker compose build inventory-service`. Then use
`BUILD_TARGET=development docker compose run --rm --no-deps inventory-service`
followed by `pytest -q`, `ruff check .`, or `ruff format --check .`.
Rebuild the default runtime image before resuming normal execution.

## Coding Style & Naming Conventions

Use Python 3.12, four-space indentation, type annotations, and Ruff's 88-character
line limit. Use `snake_case` for modules and functions and `PascalCase` for classes.
Keep route handlers small. Commit dependency changes together with the updated
service `uv.lock`.

## Testing Guidelines

Use pytest and name files `test_*.py` and functions `test_*`. Health tests cover
successful queries and database failures through HTTPX's ASGI transport. Verify
real PostgreSQL behavior through Compose as well. No coverage threshold is set.

## Commit & Pull Request Guidelines

No Git history or established commit convention exists yet. Prefer concise,
imperative messages, optionally prefixed with `feat:`, `fix:`, or `docs:`. Pull
requests should describe behavior, link relevant issues, and report validation.

## Security & Configuration

Never commit `.env` or real credentials. Keep PostgreSQL internal to Docker.
Alembic is installed but migrations and Saga components are deferred.
