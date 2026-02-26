# Docker Configuration

> DevOps documentation for Docker setup, profiles, DooD vs DinD, and memory limits.

---

## Docker Compose Architecture

The project uses a **single unified `docker-compose.yml`** with service profiles (Compose v2 syntax, no `version` key). Each agent is a separate service activated via `--profile`.

### Service Profiles

| Profile     | Service     | Container Name  | Port  | Memory Limit | Base Image            |
|-------------|-------------|-----------------|-------|--------------|-----------------------|
| `zeroclaw`  | zeroclaw    | claw-zeroclaw   | 3100  | 512 MB       | debian:bookworm-slim  |
| `nanoclaw`  | nanoclaw    | claw-nanoclaw   | 3200  | 1 GB         | node:20-slim          |
| `picoclaw`  | picoclaw    | claw-picoclaw   | 3300  | 128 MB       | alpine:3.19           |
| `openclaw`  | openclaw    | claw-openclaw   | 3400  | 4 GB         | node:22-slim          |
| `finetune`  | finetune    | claw-finetune   | -     | (GPU)        | nvidia/cuda:12.1.1    |

### Starting Agents

```bash
# Single agent
docker compose --profile zeroclaw up -d

# Multiple agents (multi-agent mode)
docker compose --profile zeroclaw --profile picoclaw up -d

# All agents (requires 8+ GB host RAM)
docker compose --profile zeroclaw --profile nanoclaw --profile picoclaw --profile openclaw up -d

# Fine-tuning (requires NVIDIA GPU)
docker compose --profile finetune run --rm finetune python train_lora.py
```

### Stopping and Cleanup

```bash
# Stop specific agent
docker compose --profile zeroclaw down

# Stop and remove volumes
docker compose --profile zeroclaw down -v

# Stop all
docker compose down --remove-orphans
```

## Dockerfile Design

### Multi-Stage Builds

**ZeroClaw** and **PicoClaw** use multi-stage builds to minimize final image size:

```
Stage 1 (builder):  Download/compile binary
Stage 2 (runtime):  Copy binary into minimal image
```

- ZeroClaw: `debian:bookworm-slim` (downloader) -> `debian:bookworm-slim` (runtime)
- PicoClaw: `golang:1.21-alpine` (builder) -> `alpine:3.19` (runtime)

### Single-Stage Builds

**NanoClaw** and **OpenClaw** are TypeScript/Node.js applications that need the full Node.js runtime and `node_modules`:

- NanoClaw: `node:20-slim` (Node.js 20+)
- OpenClaw: `node:22-slim` (Node.js 22, pnpm)

### Security Practices

- All containers run as **non-root** users (`useradd`/`adduser`)
- `tini` is used as PID 1 init process for proper signal handling
- `--no-install-recommends` used for apt packages to minimize image size
- Each Dockerfile includes `ca-certificates` for TLS verification

## DooD vs DinD for NanoClaw

NanoClaw requires Docker for its agent sandboxing (container isolation). Two approaches are available:

### DooD (Docker-outside-of-Docker) — Default

The NanoClaw container mounts the host's Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

**Pros:**
- Simple setup — no additional containers needed
- Shares host Docker cache (faster image pulls)
- Lower resource overhead

**Cons:**
- NanoClaw containers run on the host Docker daemon
- Less isolation — NanoClaw can see other host containers
- Security risk if the agent is compromised

**When to use:** Development, testing, trusted environments.

### DinD (Docker-in-Docker) — Secure Alternative

Use a `docker:dind` sidecar service (not configured by default):

```yaml
services:
  nanoclaw-dind:
    image: docker:dind
    privileged: true
    environment:
      DOCKER_TLS_CERTDIR: /certs
    volumes:
      - nanoclaw-docker-certs:/certs
    profiles:
      - nanoclaw-dind

  nanoclaw:
    environment:
      DOCKER_HOST: tcp://nanoclaw-dind:2376
      DOCKER_TLS_VERIFY: 1
    depends_on:
      - nanoclaw-dind
```

**Pros:**
- Full isolation — separate Docker daemon
- Host Docker daemon is protected
- Better for production/untrusted environments

**Cons:**
- More complex setup
- Higher resource usage (extra daemon)
- No shared image cache

**When to use:** Production, multi-tenant, untrusted agent workloads.

## Memory Limits

Memory limits are configured via `deploy.resources.limits` in docker-compose.yml:

| Agent     | Idle Memory | Active Memory | Docker Limit | Reservation |
|-----------|-------------|---------------|--------------|-------------|
| ZeroClaw  | ~8 MB       | ~100 MB       | 512 MB       | 64 MB       |
| NanoClaw  | ~120 MB     | ~500 MB       | 1 GB         | 128 MB      |
| PicoClaw  | ~8 MB       | ~30 MB        | 128 MB       | 16 MB       |
| OpenClaw  | ~1.2 GB     | ~4 GB         | 4 GB         | 1 GB        |

**Host RAM Requirements:**
- Single agent: 2 GB minimum (PicoClaw), 8 GB recommended (OpenClaw)
- Multi-agent (all 4): 8 GB minimum, 16 GB recommended
- With fine-tuning: Add GPU VRAM (8-48 GB depending on model)

## Health Checks

Each service has a Docker health check configured:

| Agent     | Health Check Command                                        | Interval | Start Period |
|-----------|-------------------------------------------------------------|----------|--------------|
| ZeroClaw  | `zeroclaw doctor`                                           | 30s      | 15s          |
| NanoClaw  | `curl -sf http://localhost:3200/health`                     | 30s      | 30s          |
| PicoClaw  | `picoclaw agent -m "ping"`                                  | 30s      | 10s          |
| OpenClaw  | `openclaw doctor`                                           | 30s      | 45s          |

Check health status:
```bash
docker inspect --format='{{.State.Health.Status}}' claw-zeroclaw
```

## Volume Mounts

Each agent has a named volume for persistent data and a bind mount for the entrypoint:

```yaml
volumes:
  - <agent>-data:/home/<agent>/.<agent>    # Persistent config/data
  - ./<agent>/entrypoint.sh:/entrypoint.sh:ro  # Entrypoint script (read-only)
```

The `.env` file is loaded via `env_file` directive and translated by each agent's entrypoint script.

## Entrypoint Pattern

Each agent's `entrypoint.sh` follows the same pattern:

1. Read unified `CLAW_*` environment variables
2. Translate to agent-specific env var names
3. Generate agent-specific config file (TOML/JSON/JSON5)
4. Optionally load LoRA adapter configuration
5. Optionally inject system prompt enrichment
6. Start the agent binary/process

This pattern allows a single `.env` file to configure any agent without manual config file editing.

---

*Generated by DevOps Engineer — Amenthyx AI Teams v3.0*
