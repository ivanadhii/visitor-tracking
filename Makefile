PLAIN := -f docker-compose.plain.yml

.PHONY: up down build rebuild restart logs logs-backend logs-frontend logs-nginx ps clean \
        plain plain-down plain-build plain-rebuild-backend plain-restart plain-logs plain-logs-backend plain-ps plain-clean

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

# ── Plain mode (tanpa AI / PyTorch) ───────────────────────────────────────────
plain:
	docker compose $(PLAIN) up -d

plain-build:
	docker compose $(PLAIN) up -d --build

plain-down:
	docker compose $(PLAIN) down

plain-rebuild-backend:
	docker compose $(PLAIN) up -d --build backend

plain-restart:
	docker compose $(PLAIN) restart

plain-logs:
	docker compose $(PLAIN) logs -f --tail 100

plain-logs-backend:
	docker compose $(PLAIN) logs -f --tail 100 backend

plain-ps:
	docker compose $(PLAIN) ps

plain-clean:
	docker compose $(PLAIN) down --volumes --remove-orphans
	docker image prune -f
