HOST          ?= 0.0.0.0
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: dev stop backend frontend install build test url

install:
	uv sync
	cd frontend && npm install

build:
	cd frontend && npm run build

stop:
	@pkill -f "uvicorn server:app" 2>/dev/null || true

backend:
	uv run uvicorn server:app --host $(HOST) --port $(BACKEND_PORT) --reload

frontend:
	cd frontend && npx vite --host $(HOST) --port $(FRONTEND_PORT)

# Run backend + frontend concurrently.
# VS Code devcontainer: http://localhost:$(FRONTEND_PORT)
# devcontainer-cli (plain Docker): run `make url` for the correct address.
dev: stop
	@trap 'kill 0' SIGINT; \
	uv run uvicorn server:app --host $(HOST) --port $(BACKEND_PORT) --reload & \
	cd frontend && npx vite --host $(HOST) --port $(FRONTEND_PORT)

url:
	@echo "http://$(shell hostname -I | awk '{print $$1}'):$(FRONTEND_PORT)"

test:
	uv run pytest tests/ -q
