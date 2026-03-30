.PHONY: up down build rebuild restart logs logs-backend logs-frontend logs-nginx ps clean

# ── Start ──────────────────────────────────────────────────────────────────────
up:
	docker compose up -d

build:
	docker compose up -d --build

# ── Stop ───────────────────────────────────────────────────────────────────────
down:
	docker compose down

# ── Rebuild specific service ───────────────────────────────────────────────────
rebuild-backend:
	docker compose up -d --build backend

rebuild-frontend:
	docker compose up -d --build frontend

rebuild-nginx:
	docker compose up -d --build nginx

# ── Restart specific service (tanpa rebuild) ───────────────────────────────────
restart-backend:
	docker compose restart backend

restart-frontend:
	docker compose restart frontend

restart:
	docker compose restart

# ── Logs ───────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f --tail 100

logs-backend:
	docker compose logs -f --tail 100 backend

logs-frontend:
	docker compose logs -f --tail 100 frontend

logs-nginx:
	docker compose logs -f --tail 100 nginx

# ── Status ─────────────────────────────────────────────────────────────────────
ps:
	docker compose ps

# ── Tuning (ubah bytetrack.yaml lalu apply tanpa rebuild) ─────────────────────
tune:
	docker compose restart backend

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	docker compose down --volumes --remove-orphans
	docker image prune -f
