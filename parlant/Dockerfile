# ===================================================================
# CLAW AGENTS PROVISIONER — Parlant Dockerfile
# ===================================================================
# Parlant: Python-based conversational AI framework with behavioral
# guidelines, journeys, and tool integration (MCP).
#
# Base: Official Parlant edge image
# Memory: ~200 MB idle, ~2 GB active | Limit: 2 GB
# Ports: 8800 (API), 8181 (MCP)
#
# Build:  docker compose --profile parlant build
# Run:    docker compose --profile parlant up -d
# ===================================================================

FROM ghcr.io/emcie-co/parlant:edge

LABEL maintainer="Mauro Tommasi <linkedin.com/in/maurotommasi>"
LABEL org.opencontainers.image.title="Claw Parlant Agent"
LABEL org.opencontainers.image.description="Parlant conversational AI with Claw provisioning"

# Install tini for proper signal handling + curl for health checks
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r parlant && useradd -r -g parlant -m -s /bin/bash parlant

# Create data directory
RUN mkdir -p /home/parlant/.parlant && chown -R parlant:parlant /home/parlant

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER parlant
WORKDIR /home/parlant

EXPOSE 8800 8181

ENTRYPOINT ["tini", "--"]
CMD ["/entrypoint.sh"]
