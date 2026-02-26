# DEVOPS Evidence Manifest

> Evidence of all deliverables produced by the DevOps Engineer for the Claw Agents Provisioner project.

---

## Manifest Summary

| # | Deliverable | File Path | Status | Notes |
|---|-------------|-----------|--------|-------|
| 1 | Unified Docker Compose | `docker-compose.yml` | DELIVERED | 4 agent profiles + finetune profile |
| 2 | ZeroClaw Dockerfile | `zeroclaw/Dockerfile` | DELIVERED | Multi-stage: download binary |
| 3 | NanoClaw Dockerfile | `nanoclaw/Dockerfile` | DELIVERED | Node.js 20, git clone, DooD |
| 4 | PicoClaw Dockerfile | `picoclaw/Dockerfile` | DELIVERED | Multi-stage: Go build, Alpine |
| 5 | OpenClaw Dockerfile | `openclaw/Dockerfile` | DELIVERED | Node.js 22, pnpm |
| 6 | ZeroClaw Vagrantfile | `zeroclaw/Vagrantfile` | DELIVERED | Ubuntu 24.04, 4GB RAM, port 3100 |
| 7 | NanoClaw Vagrantfile | `nanoclaw/Vagrantfile` | DELIVERED | Ubuntu 24.04, 2GB RAM, Docker in VM |
| 8 | PicoClaw Vagrantfile | `picoclaw/Vagrantfile` | DELIVERED | Ubuntu 24.04, 512MB RAM, minimal |
| 9 | OpenClaw Vagrantfile | `openclaw/Vagrantfile` | DELIVERED | Ubuntu 24.04, 4GB RAM, port 3400 |
| 10 | ZeroClaw Install Script | `zeroclaw/install-zeroclaw.sh` | DELIVERED | Binary download + Rust fallback + systemd |
| 11 | NanoClaw Install Script | `nanoclaw/install-nanoclaw.sh` | DELIVERED | Node.js 20 + Docker + git clone + systemd |
| 12 | PicoClaw Install Script | `picoclaw/install-picoclaw.sh` | DELIVERED | Go install + build from source + systemd |
| 13 | OpenClaw Install Script | `openclaw/install-openclaw.sh` | DELIVERED | Node.js 22 + pnpm + git clone + systemd |
| 14 | Unified Launcher CLI | `claw.sh` | DELIVERED | Full CLI with all commands |
| 15 | Finetune Dockerfile | `finetune/Dockerfile.finetune` | DELIVERED | CUDA 12.1, Python 3.11, PEFT, bitsandbytes |
| 16 | CI/CD Pipeline | `.github/workflows/ci.yml` | DELIVERED | Matrix build, linting, security scan |
| 17 | CI/CD Documentation | `.team/devops/CICD_PIPELINE.md` | DELIVERED | Pipeline architecture docs |
| 18 | Docker Documentation | `.team/devops/DOCKER_CONFIG.md` | DELIVERED | Profiles, DooD/DinD, memory limits |
| 19 | Evidence Manifest | `.team/evidence/manifests/DEVOPS_manifest.md` | DELIVERED | This file |

## Pre-Existing Files Preserved

The following files were already present in the repository (created by other team members) and were left intact:

| File | Author | Notes |
|------|--------|-------|
| `zeroclaw/entrypoint.sh` | Full-Stack Engineer | Comprehensive env translation, 275 lines |
| `nanoclaw/entrypoint.sh` | Full-Stack Engineer | Source patching, CLAUDE.md enrichment, 310 lines |
| `shared/provision-base.sh` | Full-Stack Engineer | Python 3.11, Docker Engine, system utils |
| `shared/healthcheck.sh` | Full-Stack Engineer | Structured JSON output, per-agent checks |

## Entrypoint Scripts Created

| File | Notes |
|------|-------|
| `picoclaw/entrypoint.sh` | Created new: env translation, JSON config generation |
| `openclaw/entrypoint.sh` | Created new: env translation, JSON5 config, skills array |

## Technical Decisions

### 1. Compose v2 Syntax
- No `version` key in `docker-compose.yml` (deprecated in Compose v2)
- Uses `deploy.resources.limits` for memory constraints

### 2. DooD Default for NanoClaw
- Docker socket mount (`/var/run/docker.sock`) for simplicity
- DinD documented as secure alternative in `DOCKER_CONFIG.md`

### 3. Multi-Stage Builds
- ZeroClaw: binary download stage -> slim runtime
- PicoClaw: Go build stage -> Alpine runtime
- Reduces final image sizes significantly

### 4. Non-Root Containers
- All 4 agent containers run as non-root users
- UIDs set to 1000 for consistency

### 5. Health Check Strategy
- ZeroClaw/OpenClaw: native `doctor` command
- NanoClaw: HTTP health endpoint
- PicoClaw: agent ping message

### 6. Install Script Pattern
- All scripts: `#!/usr/bin/env bash` + `set -euo pipefail`
- All scripts: idempotent (safe to run multiple times)
- All scripts: systemd service creation with security hardening
- All scripts: colored output with `[agent]` prefix

### 7. Vagrant Networking
- Each agent gets a unique private network IP (192.168.56.10-13)
- Port forwarding with `auto_correct: true`
- Synced folders for project files and shared scripts

### 8. CI Pipeline Design
- Matrix strategy for Docker builds (4 parallel jobs)
- `continue-on-error: true` for builds (upstream repos may be unavailable)
- Security scan runs on every push (no secrets in tracked files)

## Verification Commands

```bash
# Validate docker-compose syntax
docker compose config --quiet

# Build all agent images
docker compose --profile zeroclaw build
docker compose --profile nanoclaw build
docker compose --profile picoclaw build
docker compose --profile openclaw build

# Run shellcheck on all scripts
find . -name "*.sh" -exec shellcheck {} \;

# Test claw.sh help
./claw.sh help

# Run health checks
./claw.sh health all
```

---

*Manifest generated: 2026-02-26*
*DevOps Engineer — Amenthyx AI Teams v3.0*
