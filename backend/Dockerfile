FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app app
COPY alembic.ini ./
COPY migrations migrations
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app app \
    && chown -R app:app /app
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/actuator/health', timeout=2)" || exit 1
CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080"]
