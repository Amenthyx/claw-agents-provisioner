# Decision Log -- Claw Agents Provisioner v2.0

> Version: 1.0
> Date: 2026-03-02
> Author: PM (Full-Stack Team, Amenthyx AI Teams v3.0)

---

## Overview

This log tracks architectural and technical decisions made during v2.0 production hardening. Each entry records the context, options considered, decision made, and rationale.

---

## Decision Template

```markdown
### D-XXX: [Decision Title]

| Attribute | Value |
|-----------|-------|
| **ID** | D-XXX |
| **Date** | YYYY-MM-DD |
| **Status** | PROPOSED / ACCEPTED / SUPERSEDED |
| **Decider** | [Role] |
| **Milestone** | M[X] |

**Context**: [What is the issue or question?]

**Options Considered**:
1. [Option A] -- [Pros/Cons]
2. [Option B] -- [Pros/Cons]
3. [Option C] -- [Pros/Cons]

**Decision**: [Which option was chosen]

**Rationale**: [Why this option was selected]

**Consequences**: [What changes as a result of this decision]
```

---

## Decisions

### D-001: QA Conditional Pass Accepted After BUG-001 Fix

| Attribute | Value |
|-----------|-------|
| **ID** | D-001 |
| **Date** | 2026-03-02 |
| **Status** | ACCEPTED |
| **Decider** | PM + QA |
| **Milestone** | M12 |

**Context**: QA Wave 3 produced a CONDITIONAL PASS verdict with 547/570 tests passing (95.96%). All 23 failures traced to a single root cause: DAL singleton SQLite path resolution in the test environment.

**Options Considered**:
1. Accept conditional pass and ship -- Risk: 23 tests remain broken, could mask future regressions
2. Fix BUG-001 first, then re-validate -- Cost: ~10 min additional work, eliminates all test failures
3. Defer to v2.1 -- Unacceptable: broken tests reduce CI value

**Decision**: Fix BUG-001 in Wave 3.5, then accept the QA sign-off as a full PASS.

**Rationale**: The fix was trivial (add `CLAW_DATA_DIR` override in conftest.py + DAL singleton reset). After the fix (commit `46e28d6`), all 570 tests pass at 100%. The conditional pass was upgraded to a full PASS.

**Consequences**: Test suite is now fully green. CI provides reliable signal. No known test failures in the codebase.

---

### D-002: V2-14 Blue-Green Deployment Deferred to v2.1

| Attribute | Value |
|-----------|-------|
| **ID** | D-002 |
| **Date** | 2026-03-02 |
| **Status** | ACCEPTED |
| **Decider** | PM + TL |
| **Milestone** | M12 |

**Context**: The v2.0 strategy included `scripts/blue-green-deploy.sh` (V2-14) as a P1 deliverable under M12. All P0 items were complete, and the team needed to decide whether to implement blue-green or ship without it.

**Options Considered**:
1. Implement blue-green deployment now -- Complex: requires load balancer orchestration, health-check-based traffic switching, and extensive testing
2. Defer to v2.1 with manual rollback as interim -- Acceptable: rollback procedures are documented and tested; smoke test covers post-deploy verification
3. Implement a simplified version (stop-start, not zero-downtime) -- Not useful: this is just the existing manual rollback, renamed

**Decision**: Defer V2-14 to v2.1. Document the gap. Use existing rollback procedures as the interim solution.

**Rationale**: Blue-green deployment is a P1 (important but not blocking). The existing rollback procedures (`.team/releases/ROLLBACK_PROCEDURES.md`) cover 8 rollback scenarios including full platform rollback. The smoke test provides automated post-deploy verification. Implementing blue-green properly requires load balancer integration that exceeds the v2.0 scope.

**Consequences**: M12 is 90% complete (9/10 deliverables). One GitHub issue remains open under M12. Manual rollback requires ~15-30 minutes of downtime for full platform rollback.

---

### D-003: FE Role Activated for v2.0

| Attribute | Value |
|-----------|-------|
| **ID** | D-003 |
| **Date** | 2026-03-02 |
| **Status** | ACCEPTED |
| **Decider** | TL + PM |
| **Milestone** | M7, M10 |

**Context**: In v1.0, the FE and MOB roles were inactive (no web UI or mobile component in scope). v2.0 required wizard UI testing and accessibility auditing for production readiness.

**Options Considered**:
1. Have BE handle wizard UI tests -- BE role already overloaded with integration tests, E2E tests, and migration system
2. Activate FE role for wizard testing -- Dedicated focus on UI testing, accessibility audit, and build optimization
3. Skip wizard UI testing -- Unacceptable for production: wizard is the primary user-facing deployment interface

**Decision**: Activate the FE role specifically for Wave 2 with scope: wizard UI tests (vitest), accessibility audit (WCAG 2.1 AA), and production build optimization.

**Rationale**: The wizard UI is the primary interface users interact with during agent provisioning. Untested UI components in production risk broken deployment flows. The FE agent delivered 14 test files, a comprehensive accessibility audit (rated B+), and build optimization with manual chunk splitting.

**Consequences**: FE delivered commit `7c8b945` with 14 test files, accessibility audit, build optimization, pre-commit hooks, and secrets rotation script.

---

### D-004: DAL Singleton Exception Handling Broadened

| Attribute | Value |
|-----------|-------|
| **ID** | D-004 |
| **Date** | 2026-03-02 |
| **Status** | ACCEPTED |
| **Decider** | BE |
| **Milestone** | M7 |

**Context**: The DAL singleton (`shared/claw_dal.py`) used a narrow exception handler that only caught `sqlite3.OperationalError`. In test environments and some deployment scenarios, `FileNotFoundError` and `PermissionError` could also occur during database initialization.

**Options Considered**:
1. Keep narrow handler, fix test environment only -- Risk: production environments with permission issues would crash
2. Broaden exception handling to catch `OSError` (parent of both `FileNotFoundError` and `PermissionError`) -- Handles all filesystem-related initialization failures gracefully
3. Add directory creation in `__init__` -- Addresses symptom but not root cause of missing `CLAW_DATA_DIR`

**Decision**: Broaden exception handling and add `CLAW_DATA_DIR` environment variable override for test isolation. The BUG-001 fix (commit `46e28d6`) adds a `conftest.py` autouse fixture that sets `CLAW_DATA_DIR` to a temp directory and resets the singleton between tests.

**Rationale**: The fix addresses both the immediate test isolation issue and the broader robustness concern. Production deployments create the data directory in Docker entrypoints, but the DAL should not crash on filesystem errors during initialization.

**Consequences**: All 570 tests pass. DAL is more resilient to filesystem issues. Test isolation is properly enforced.

---

### D-005: Secrets Rotation Automation Added to Vault

| Attribute | Value |
|-----------|-------|
| **ID** | D-005 |
| **Date** | 2026-03-02 |
| **Status** | ACCEPTED |
| **Decider** | FE + INFRA |
| **Milestone** | M10 |

**Context**: v1.0 had no mechanism for rotating API keys and auth tokens without downtime. For production deployment, secrets rotation is a security requirement.

**Options Considered**:
1. Manual rotation with documentation -- Error-prone, requires downtime
2. Automated rotation script with zero-downtime reload -- Script rotates secrets, restarts affected containers gracefully
3. HashiCorp Vault integration -- Overkill for current scale; adds infrastructure complexity

**Decision**: Create `scripts/rotate-secrets.sh` that rotates specified secrets in Docker secrets and gracefully reloads affected services without downtime.

**Rationale**: The script provides a balanced solution: automated enough to prevent human error, simple enough to not require additional infrastructure. It works with Docker secrets which are already used in `docker-compose.production.yml`.

**Consequences**: Secrets can be rotated without downtime. The script is documented in the runbook. Pre-commit hooks prevent committing secrets to the repository.

---

*Decision Log v2.0 -- Claw Agents Provisioner v2.0 -- Amenthyx AI Teams v3.0*
*FINAL -- 5 decisions recorded -- Project CLOSED 2026-03-02*
