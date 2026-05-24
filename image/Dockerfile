FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# System deps (curl for healthcheck + builds that need gcc can be added if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy only dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock ./

# Create venv + install deps (no dev deps, pinned, reproducible)
RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev

# Now copy the actual app code
COPY . .

ENV PORT=8000
# Disable guardrails-ai OTLP telemetry exporters and hub update checks.
# guardrails-ai 0.10.x initialises OpenTelemetry OTLP exporters at startup
# that attempt outbound connections. In a private VPC those connections hang
# until TCP timeout, blocking the FastAPI lifespan and preventing health checks.
ENV OTEL_SDK_DISABLED=true \
    GUARDRAILS_DISABLE_ANALYTICS=true \
    GUARDRAILS_NO_UPDATE_CHECK=true
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uv run uvicorn server:api --host 0.0.0.0 --port ${PORT}"]
