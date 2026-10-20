FROM python:3.13-slim
WORKDIR /app
RUN --mount=type=secret,id=network_ca \
    if [ -f /run/secrets/network_ca ]; then export PIP_CERT=/run/secrets/network_ca; fi; \
    pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=network_ca \
    if [ -f /run/secrets/network_ca ]; then export SSL_CERT_FILE=/run/secrets/network_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN --mount=type=secret,id=network_ca \
    if [ -f /run/secrets/network_ca ]; then export SSL_CERT_FILE=/run/secrets/network_ca; fi; \
    uv sync --frozen --no-dev && useradd --uid 10001 --create-home fk && chmod -R a+rX /app \
    && mkdir -p /var/lib/forest-keeper/imports /var/lib/forest-keeper/upload-tmp \
    && chown fk:fk /var/lib/forest-keeper/imports /var/lib/forest-keeper/upload-tmp \
    && chmod 700 /var/lib/forest-keeper/imports /var/lib/forest-keeper/upload-tmp
USER fk
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
