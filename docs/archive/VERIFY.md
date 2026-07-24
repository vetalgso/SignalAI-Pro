# SignalAI Pro v0.2.0 verification

```bash
docker compose down -v
docker compose up --build -d
docker compose ps
docker compose logs api --tail=100
curl http://localhost:8000/health
docker compose exec api alembic current
docker compose exec db psql -U signalai -d signalai -c '\dt'
```

Expected Alembic revision: `20260724_0001 (head)`.
Expected tables: `alembic_version`, `signals`, `users`.
