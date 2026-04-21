HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: dev url

# Run the Chainlit dev server with file watching.
#
# Accessing from the host browser:
#   - VS Code devcontainer: ports are auto-forwarded, use http://localhost:8000
#   - devcontainer-cli (plain Docker, no VS Code): forwardPorts is ignored,
#     use the container's bridge IP instead:
#
#       make url          # prints the correct URL
#
#     or manually: http://$(hostname -I | awk '{print $1}'):8000
dev:
	uv run watchfiles "uv run chainlit run app.py --host $(HOST) --port $(PORT) -h" .

# Print the URL to open in the host browser when running via devcontainer-cli.
url:
	@echo "http://$(shell hostname -I | awk '{print $$1}'):$(PORT)"
