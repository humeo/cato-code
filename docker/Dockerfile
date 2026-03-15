FROM python:3.12-slim

# Install system deps: Docker CLI (to manage catocode-worker container)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
       https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Install Python deps only (layer-cached, re-runs only when pyproject.toml/uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY src/ src/
RUN uv sync --frozen --no-dev \
    && ln -s /app/.venv/bin/catocode /usr/local/bin/catocode

# Data directory
RUN mkdir -p /data
ENV CATOCODE_DB_PATH=/data/catocode.db

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/catocode"]
CMD ["server", "--port", "8000"]
