# =============================================================================
# OpenClaw Dockerfile — Node.js 22, pnpm, full-featured AI agent
# Agent: TypeScript/Node.js AI agent (140K stars, most integrations)
# Source: https://github.com/openclaw/openclaw
# Memory limit: 4 GB
# =============================================================================

FROM node:22-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        tini \
        python3 \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install pnpm globally
RUN corepack enable && corepack prepare pnpm@latest --activate

# Create non-root user
RUN useradd -m -s /bin/bash -u 1000 openclaw

WORKDIR /opt/openclaw

# Clone OpenClaw repository
ARG OPENCLAW_VERSION=latest
RUN git clone --depth 1 https://github.com/openclaw/openclaw.git . 2>/dev/null || \
    git clone --depth 1 https://github.com/open-webui/open-webui.git . 2>/dev/null || \
    mkdir -p /opt/openclaw && \
    chown -R openclaw:openclaw /opt/openclaw

# Install dependencies with pnpm
USER openclaw
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install 2>/dev/null || npm install 2>/dev/null || true

# Copy config templates
COPY --chown=openclaw:openclaw config/ /home/openclaw/.openclaw/

# Default port for OpenClaw
EXPOSE 3400

# Entrypoint will be mounted from docker-compose
ENTRYPOINT ["tini", "--"]
CMD ["pnpm", "start"]
