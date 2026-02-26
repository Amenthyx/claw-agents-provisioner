# =============================================================================
# ZeroClaw Dockerfile — Multi-stage: download pre-built binary
# Agent: Rust-based AI agent | Memory limit: 512 MB
# Source: https://github.com/zeroclaw-labs/zeroclaw
# =============================================================================

# -- Stage 1: Download pre-built binary --
FROM debian:bookworm-slim AS downloader

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ARG ZEROCLAW_VERSION=latest

# Download the latest release binary from GitHub
RUN set -eux; \
    if [ "${ZEROCLAW_VERSION}" = "latest" ]; then \
        DOWNLOAD_URL="https://github.com/zeroclaw-labs/zeroclaw/releases/latest/download/zeroclaw-linux-x86_64"; \
    else \
        DOWNLOAD_URL="https://github.com/zeroclaw-labs/zeroclaw/releases/download/v${ZEROCLAW_VERSION}/zeroclaw-linux-x86_64"; \
    fi; \
    curl -fsSL -o /usr/local/bin/zeroclaw "${DOWNLOAD_URL}" || \
    curl -fsSL -o /usr/local/bin/zeroclaw "https://github.com/zeroclaw-labs/zeroclaw/releases/latest/download/zeroclaw-x86_64-unknown-linux-gnu" || \
    echo "WARN: Binary download failed — will attempt build from source at runtime"; \
    chmod +x /usr/local/bin/zeroclaw 2>/dev/null || true

# -- Stage 2: Minimal runtime image --
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tini && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash -u 1000 zeroclaw

# Copy binary from downloader stage
COPY --from=downloader /usr/local/bin/zeroclaw /usr/local/bin/zeroclaw

# Copy config template
COPY config/ /home/zeroclaw/.zeroclaw/

# Set ownership
RUN chown -R zeroclaw:zeroclaw /home/zeroclaw

USER zeroclaw
WORKDIR /home/zeroclaw

# Default port for ZeroClaw
EXPOSE 3100

# Entrypoint will be mounted from docker-compose
ENTRYPOINT ["tini", "--"]
CMD ["zeroclaw", "serve"]
