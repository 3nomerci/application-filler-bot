FROM ghcr.io/astral-sh/uv:0.10.3@sha256:7a88d4c4e6f44200575000638453a5a381db0ae31ad5c3a51b14f8687c9d93a3 AS uv
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && useradd --create-home --uid 10001 runner

FROM base AS gateway
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
USER runner
ENTRYPOINT ["/app/.venv/bin/python", "-m", "application_filler.gateway"]

FROM base AS runtime
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers DISPLAY=:99 HOME=/tmp/home FILLER_IN_DOCKER=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc novnc websockify openbox tini fonts-dejavu-core \
    && uv run --frozen --no-sync playwright install --with-deps chromium \
    && rm -rf /tmp/uv-cache /var/lib/apt/lists/*
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY examples ./examples
COPY docker/entrypoint.sh /entrypoint.sh
RUN mkdir -p /app/private /app/artifacts && chown runner:runner /app/private /app/artifacts \
    && chmod 755 /entrypoint.sh
USER runner
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["run", "--links", "private/links.txt", "--interactive"]

FROM runtime AS test
USER root
RUN uv sync --frozen --extra dev --no-editable
COPY tests ./tests
USER runner
ENTRYPOINT ["/usr/bin/tini", "--", "/app/.venv/bin/pytest"]
CMD ["-q", "-p", "no:cacheprovider", "--basetemp", "/tmp/pytest"]
