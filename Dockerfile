# We use the official uv image which includes python and uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Configuration
ENV UV_COMPILE_BYTECODE=1 
ENV UV_LINK_MODE=copy 
ENV UV_NO_DEV=1
WORKDIR /app

# Install project
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src
COPY aware-protos/ ./aware-protos
RUN uv sync --locked --no-editable

# -- Runtime --
FROM python:3.13-slim-bookworm

# Create a non-privileged user
RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# This calls the "instance-pred" script defined in your pyproject.toml
CMD ["instance-pred", "serve"]