HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: dev

dev:
	uv run watchfiles "uv run chainlit run app.py --host $(HOST) --port $(PORT) -h" .
