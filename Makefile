# --- Configuration ---
SERVICE_NAME := intent-engine
SHELL := /bin/bash

# --- Help ---
.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Init & Submodules ---
.PHONY: install
init: ## Initialize submodules and install local dependencies
	@echo "Initializing Git submodules..."
	git submodule update --init --recursive
	@echo "Installing dependencies with uv..."
	uv sync --frozen

# --- Docker Operations (Real-time) ---
.PHONY: build
build: ## Force a rebuild of the docker image
	@echo "Building docker images..."
	docker compose build

.PHONY: dev
dev: ## Run with Terminal UI (Interactive mode with TTY)
	@echo "🖥️  Starting interactive session with Rich UI..."
	# 'run' allocates a TTY by default. --service-ports ensures FastAPI is reachable.
	docker compose run --rm --service-ports $(SERVICE_NAME)

.PHONY: serve
serve: ## Run headless in background (Builds image first)
	@echo "Starting headless server..."
	docker compose up --build -d
	@echo "Follow logs with: make logs"

.PHONY: logs
logs: ## Follow docker logs
	docker compose logs -f $(SERVICE_NAME)

.PHONY: stop
stop: ## Stop all docker containers
	docker compose down

# --- Offline Processing (CLI) ---

.PHONY: bulk
bulk: ## Run bulk processing (e.g. make bulk FILE=session.parquet)
	instance-pred bulk

# --- Local Development (No Docker) ---
.PHONY: clean
clean: ## Remove temporary files, caches, and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .venv
	rm -rf build/
	rm -rf dist/