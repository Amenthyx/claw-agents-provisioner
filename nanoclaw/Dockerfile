# =============================================================================
# NanoClaw Dockerfile — Clone repo, install Node.js 20+, Docker socket mount
# Agent: TypeScript AI agent with container isolation (DooD)
# Source: https://github.com/qwibitai/nanoclaw
# Memory limit: 1 GB
# =============================================================================

FROM node:20-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        tini \
        docker.io && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user and add to docker group for DooD
RUN useradd -m -s /bin/bash -u 1000 nanoclaw && \
    groupadd -f docker 2>/dev/null || true && \
    usermod -aG docker nanoclaw

WORKDIR /opt/nanoclaw

# Clone NanoClaw repository
ARG NANOCLAW_COMMIT=main
RUN git clone --depth 1 --branch "${NANOCLAW_COMMIT}" \
    https://github.com/qwibitai/nanoclaw.git . && \
    chown -R nanoclaw:nanoclaw /opt/nanoclaw

# Install dependencies
USER nanoclaw
RUN npm install --production 2>/dev/null || npm install || true

# Copy config templates
COPY --chown=nanoclaw:nanoclaw config/ /home/nanoclaw/.nanoclaw/

# Default port for NanoClaw
EXPOSE 3200

# Entrypoint will be mounted from docker-compose
ENTRYPOINT ["tini", "--"]
CMD ["node", "src/index.js"]
