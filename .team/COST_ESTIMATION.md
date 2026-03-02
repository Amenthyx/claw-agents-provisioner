# Cost Estimation — Claw Agents Provisioner v2.0 Production Hardening
## Date: 2026-03-02T21:00:00Z
## Team: Full-Stack Team (v3.0)
## Strategy: ./STRATEGY.md

---

### 1. Token & AI Cost Estimate

| Wave | Agents | Est. Input Tokens | Est. Output Tokens | Est. Cost (USD) |
|------|--------|-------------------|--------------------|--------------------|
| Wave 0 | TL | ~5K | ~10K | $0.50 |
| Wave 1 | PM | ~30K | ~50K | $3.00 |
| Wave 1.5 | LEGAL | ~15K | ~20K | $1.50 |
| Wave 2 | BE + DEVOPS + INFRA + FE (4 agents) | ~200K | ~300K | $15.00 |
| Wave 2.5 | PM (reporting) | ~10K | ~15K | $1.00 |
| Wave 3 | QA | ~50K | ~80K | $5.00 |
| Wave 3.5 | Bug Fix (conditional) | ~20K | ~30K | $1.50 |
| Wave 4 | RM | ~20K | ~30K | $2.00 |
| Wave 5 | PM (final) | ~10K | ~15K | $1.00 |
| **TOTAL** | **~10 agents** | **~360K** | **~550K** | **$30.50** |

**Model**: Claude Opus 4.6 (primary), Claude Sonnet 4.6 (parallel agents)
**Pricing basis**: Opus input $15/MTok, output $75/MTok; Sonnet input $3/MTok, output $15/MTok
**Buffer**: 10% contingency included

---

### 2. External Service Costs

| Service | Cost | Payment Required? | Pre-Approved? |
|---------|------|-------------------|---------------|
| GitHub Actions | $0 (free tier) | No | Yes |
| Docker Hub | $0 (public images) | No | Yes |
| Let's Encrypt | $0 (free) | No | Yes |
| Prometheus | $0 (self-hosted) | No | Yes |
| Grafana | $0 (self-hosted) | No | Yes |
| Loki | $0 (self-hosted) | No | Yes |
| k6 (open source) | $0 | No | Yes |
| Trivy | $0 (open source) | No | Yes |
| Bandit | $0 (open source) | No | Yes |
| **TOTAL** | **$0** | **No** | **Yes** |

---

### 3. Infrastructure Costs

| Resource | Cost | Notes |
|----------|------|-------|
| Compute | $0 | All development on local machine |
| Docker containers | $0 | Local Docker Desktop |
| CI/CD | $0 | GitHub Actions free tier (2,000 min/month) |
| Storage | $0 | Local disk |
| SSL Certificates | $0 | Let's Encrypt |
| **TOTAL** | **$0** | |

---

### 4. Agent Allocation per Wave

#### Wave 1: Planning (PM only)
- Update PROJECT_CHARTER.md for v2.0
- Create MILESTONES.md (M1-M6)
- Create/update KANBAN.md
- Create GitHub issues for all P0 features
- Generate initial PPTX + PDF report

#### Wave 1.5: Compliance (LEGAL only, background)
- GDPR compliance checklist
- SOC2 audit trail verification
- HIPAA readiness assessment
- License compliance for monitoring stack (Prometheus, Grafana, Loki)

#### Wave 2: Engineering (4 agents in parallel)

| Agent | Scope | Key Deliverables |
|-------|-------|-----------------|
| **BE** | Integration tests, E2E test framework, database migrations, backup/restore | `tests/test_integration_*.py`, `tests/test_e2e_*.py`, `scripts/migrate.py`, `scripts/backup.sh`, `scripts/restore.sh` |
| **DEVOPS** | Production Docker Compose, nginx TLS proxy, monitoring stack (Prometheus + Grafana + Loki), smoke tests | `docker-compose.production.yml`, `nginx/`, `monitoring/`, `scripts/smoke-test.sh` |
| **INFRA** | CI/CD hardening, pre-commit hooks, security scanning (Bandit), branch protection, secrets management | `.github/workflows/ci.yml` updates, `.pre-commit-config.yaml`, `scripts/security-scan.sh` |
| **FE** | Wizard UI tests (vitest), accessibility audit, production build optimization | `wizard/src/**/*.test.tsx`, `wizard/vitest.config.ts` |

#### Wave 3: QA (sequential gate)
- Run full test pyramid: static → unit → integration → E2E → performance → security
- k6 load test scripts for router, memory, RAG, dashboard
- Generate coverage reports and evidence artifacts
- QA sign-off or bug report

#### Wave 4: Release (after QA pass)
- Operational runbook
- Release checklist and changelog
- Rollback procedures
- GitHub Release creation

#### Wave 5: Final Reporting
- Final PPTX + PDF with evidence dashboards
- Close all GitHub milestones
- Summary presentation to user

---

### 5. Risk-Adjusted Total

| Scenario | Probability | Cost |
|----------|------------|------|
| Happy path (no bugs) | 30% | $25.00 |
| Minor bug fixes (1 QA loop) | 50% | $30.50 |
| Major rework (2 QA loops) | 15% | $35.00 |
| Critical issues (3+ loops) | 5% | $40.00 |
| **Expected value** | | **$30.25** |

---

### 6. Summary

| Category | Cost |
|----------|------|
| AI/Token costs | ~$30.50 |
| External services | $0 |
| Infrastructure | $0 |
| **Grand Total** | **~$30.50** |

**Within strategy budget tolerance**: $30.50 is at the $30 threshold. If approved, we proceed. If too high, we can:
1. Use Sonnet for all Wave 2 agents instead of Opus (-$8, total ~$22)
2. Skip Wave 1.5 Legal (-$1.50, total ~$29)
3. Reduce FE scope (skip wizard UI tests, -$3, total ~$27)

---

*Cost Estimation v1.0 — Claw Agents Provisioner v2.0 — Full-Stack Team v3.0*
*BLOCKING GATE: User approval required before Wave 1 begins.*
