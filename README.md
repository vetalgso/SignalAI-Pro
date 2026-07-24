# SignalAI Pro

Backend foundation for an AI-assisted trading signals platform.

## Database migrations

The database schema is managed only by Alembic. The API container runs
`alembic upgrade head` before starting Uvicorn.

For the first start of version 0.2.0, reset the old development volume because
the previous version created tables with `Base.metadata.create_all()`:

```bash
docker compose down -v
docker compose up --build -d
```

## Verify

```bash
docker compose ps
docker compose logs api --tail=100
curl http://localhost:8000/health
docker compose exec api alembic current
docker compose exec api alembic history
docker compose exec db psql -U signalai -d signalai -c '\dt'
```

Expected tables include `alembic_version`, `signals`, and `users`.

Swagger UI: http://localhost:8000/docs

## Migration commands

Create a migration after changing ORM models:

```bash
docker compose exec api alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
docker compose exec api alembic upgrade head
```

Rollback one migration:

```bash
docker compose exec api alembic downgrade -1
```

This release does not place real trades.
