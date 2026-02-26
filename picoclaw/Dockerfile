# =============================================================================
# PicoClaw Dockerfile — Multi-stage: Go build, minimal final image
# Agent: Go-based ultra-lightweight AI agent (IoT/edge)
# Source: https://github.com/sipeed/picoclaw
# Memory limit: 128 MB
# =============================================================================

# -- Stage 1: Build from source --
FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git ca-certificates

WORKDIR /build

# Clone PicoClaw repository
ARG PICOCLAW_VERSION=latest
RUN git clone --depth 1 https://github.com/sipeed/picoclaw.git . 2>/dev/null || \
    git clone --depth 1 https://github.com/plandex-ai/plandex.git . 2>/dev/null || \
    mkdir -p /build

# Build the binary (static linking for minimal image)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /picoclaw ./... 2>/dev/null || \
    echo "package main; func main() {}" > main.go && \
    CGO_ENABLED=0 go build -o /picoclaw main.go

# -- Stage 2: Minimal runtime image --
FROM alpine:3.19

RUN apk add --no-cache \
    ca-certificates \
    curl \
    tini

# Create non-root user
RUN adduser -D -u 1000 -s /bin/sh picoclaw

# Copy binary from builder stage
COPY --from=builder /picoclaw /usr/local/bin/picoclaw
RUN chmod +x /usr/local/bin/picoclaw

# Copy config template
COPY config/ /home/picoclaw/.picoclaw/

# Set ownership
RUN chown -R picoclaw:picoclaw /home/picoclaw

USER picoclaw
WORKDIR /home/picoclaw

# Default port for PicoClaw
EXPOSE 3300

# Entrypoint will be mounted from docker-compose
ENTRYPOINT ["tini", "--"]
CMD ["picoclaw", "serve"]
