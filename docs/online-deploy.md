# Crypt Clash Online Deployment (Docker)

## Overview

This deploy target runs:

- `api`: FastAPI server (`cryptclash server`)
- `db`: Postgres for accounts/characters/parties/instances
- `redis`: optional cache/queue backend (reserved for scale paths)
- `caddy`: TLS reverse proxy for `/api/*` and `/ws/*`

## Quick Start

1. Copy environment template:

```bash
cp .env.example .env
```

2. Set real values in `.env`:
   - `CRYPTCLASH_DOMAIN` to your domain
   - `CRYPTCLASH_JWT_SECRET` to a strong random secret
   - Keep `CRYPTCLASH_DATABASE_URL` pointed at the `db` service unless external Postgres is used

3. Start services:

```bash
./scripts/run-online-docker.sh
```

4. Confirm API health (example endpoint):

```bash
curl -X POST https://<your-domain>/api/auth/register \
  -H "content-type: application/json" \
  -d '{"username":"demo-user","password":"demo-password-123"}'
```

## VPS Baseline

- 2 vCPU, 4 GB RAM, 60 GB SSD for early access
- Ubuntu 22.04+ with Docker Engine and Compose plugin
- DNS A/AAAA record pointing your domain to the VPS

## TLS + Domain

- Caddy automatically provisions certificates when:
  - `CRYPTCLASH_DOMAIN` is valid
  - ports `80` and `443` are open

## Backups

- Postgres data volume: `postgres_data`
- Backup command example:

```bash
docker exec -t $(docker ps --filter name=db --format '{{.ID}}') \
  pg_dump -U cryptclash cryptclash > backup-cryptclash.sql
```

- Restore command example:

```bash
cat backup-cryptclash.sql | docker exec -i $(docker ps --filter name=db --format '{{.ID}}') \
  psql -U cryptclash -d cryptclash
```

## Logs

- API: `docker compose logs -f api`
- DB: `docker compose logs -f db`
- Caddy: `docker compose logs -f caddy`

## Migrations

Initial migration files live in `alembic/`.

Run migrations against your configured database:

```bash
alembic upgrade head
```
