# Crypt Clash Online (No Docker)

## Goal

Run the MMO-lite server directly on your machine with Python and a local database, while keeping Docker files available for later.

## Install

```bash
cd /Users/brianvassell/DND-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,online]"
```

## Environment

Create `.env.local` (optional). If omitted, defaults are used (`sqlite+aiosqlite:///./cryptclash.db`).

Example:

```bash
cat > .env.local <<'EOF'
CRYPTCLASH_DATABASE_URL=sqlite+aiosqlite:///./cryptclash.db
CRYPTCLASH_JWT_SECRET=dev-change-me
CRYPTCLASH_ACCESS_TOKEN_MINUTES=30
CRYPTCLASH_REFRESH_TOKEN_DAYS=14
CRYPTCLASH_PRESENCE_LIMIT=50
CRYPTCLASH_REACTION_LIMIT_COUNT=4
CRYPTCLASH_REACTION_LIMIT_WINDOW_SECONDS=10
CRYPTCLASH_RECONNECT_GRACE_SECONDS=60
CRYPTCLASH_MOTD=Welcome to Crypt Clash Online (Local)
CRYPTCLASH_PORT=8000
EOF
```

## Start Server

Option A:

```bash
./scripts/run-online-local.sh
```

Option B:

```bash
source .venv/bin/activate
set -a && source .env.local && set +a
cryptclash server --host 0.0.0.0 --port 8000
```

## Client Workflow

In another terminal:

```bash
cd /Users/brianvassell/DND-cli
source .venv/bin/activate
cryptclash register --server http://127.0.0.1:8000 --username iris
cryptclash character create --name Iris --archetype Mage
cryptclash online --server http://127.0.0.1:8000
```
