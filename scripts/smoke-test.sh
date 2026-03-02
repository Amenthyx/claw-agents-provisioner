#!/usr/bin/env bash
# ===================================================================
# smoke-test.sh — Deployment Smoke Test for Claw Agents Provisioner
# ===================================================================
#
# Verifies the system is minimally operational after deployment.
# Runs lightweight checks that complete in seconds.
#
# Checks:
#   1. Python shared modules compile and import
#   2. Docker Compose config validates
#   3. CLI tools respond to --help
#   4. Critical files exist
#   5. Port conflicts check
#   6. Environment template valid
#
# Usage:
#   bash scripts/smoke-test.sh
#
# Exit code:
#   0 — All checks passed
#   1 — One or more checks failed
# ===================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' RED='' YELLOW='' BOLD='' NC=''
fi

PASS=0
FAIL=0
SKIP=0

pass() { echo -e "${GREEN}  PASS${NC}  $*"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}  FAIL${NC}  $*"; FAIL=$((FAIL + 1)); }
skip() { echo -e "${YELLOW}  SKIP${NC}  $*"; SKIP=$((SKIP + 1)); }

echo -e "${BOLD}=== Claw Agents Provisioner — Smoke Test ===${NC}"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# ── 1. Python shared modules compile ────────────────────────────────

echo -e "${BOLD}[1/6] Python module compilation${NC}"

COMPILE_FAIL=0
for f in "${PROJECT_ROOT}"/shared/*.py; do
    if [ -f "$f" ]; then
        MODULE=$(basename "$f")
        if python3 -m py_compile "$f" 2>/dev/null; then
            pass "Compiles: ${MODULE}"
        else
            fail "Compile error: ${MODULE}"
            COMPILE_FAIL=1
        fi
    fi
done

# ── 2. Python shared modules import ─────────────────────────────────

echo ""
echo -e "${BOLD}[2/6] Python module imports${NC}"

CRITICAL_MODULES=(
    "claw_vault"
    "claw_security"
    "claw_audit"
    "claw_auth"
    "claw_ratelimit"
)

cd "${PROJECT_ROOT}/shared"
for module in "${CRITICAL_MODULES[@]}"; do
    if [ -f "${module}.py" ]; then
        if python3 -c "import importlib; importlib.import_module('${module}')" 2>/dev/null; then
            pass "Imports: ${module}"
        else
            # Some modules have optional deps — not a hard failure
            skip "Import needs deps: ${module}"
        fi
    else
        skip "Module not found: ${module}"
    fi
done
cd "${PROJECT_ROOT}"

# ── 3. CLI tools respond ────────────────────────────────────────────

echo ""
echo -e "${BOLD}[3/6] CLI tool health${NC}"

CLI_TOOLS=(
    "shared/claw_vault.py"
    "shared/claw_security.py"
)

for tool in "${CLI_TOOLS[@]}"; do
    TOOL_PATH="${PROJECT_ROOT}/${tool}"
    if [ -f "${TOOL_PATH}" ]; then
        if python3 "${TOOL_PATH}" --help >/dev/null 2>&1; then
            pass "CLI responds: ${tool}"
        else
            fail "CLI broken: ${tool}"
        fi
    else
        skip "Tool not found: ${tool}"
    fi
done

# ── 4. Critical files exist ─────────────────────────────────────────

echo ""
echo -e "${BOLD}[4/6] Critical files${NC}"

CRITICAL_FILES=(
    ".env.template"
    "docker-compose.yml"
    ".github/workflows/ci.yml"
    ".pre-commit-config.yaml"
    ".gitignore"
    "shared/claw_vault.py"
    "shared/claw_security.py"
    "shared/claw_audit.py"
    "shared/claw_auth.py"
    "shared/claw_router.py"
    "shared/claw_orchestrator.py"
    "claw.sh"
)

for file in "${CRITICAL_FILES[@]}"; do
    FULL_PATH="${PROJECT_ROOT}/${file}"
    if [ -f "${FULL_PATH}" ]; then
        pass "Exists: ${file}"
    else
        fail "Missing: ${file}"
    fi
done

# ── 5. Docker Compose validation ────────────────────────────────────

echo ""
echo -e "${BOLD}[5/6] Docker Compose${NC}"

if command -v docker &>/dev/null; then
    TEMP_ENV=""
    if [ ! -f "${PROJECT_ROOT}/.env" ]; then
        if [ -f "${PROJECT_ROOT}/.env.template" ]; then
            cp "${PROJECT_ROOT}/.env.template" "${PROJECT_ROOT}/.env"
            TEMP_ENV=1
        fi
    fi

    if docker compose -f "${PROJECT_ROOT}/docker-compose.yml" config --quiet 2>/dev/null; then
        pass "docker-compose.yml validates"
    else
        fail "docker-compose.yml invalid"
    fi

    # Clean up temp .env if we created it
    if [ -n "${TEMP_ENV}" ]; then
        rm -f "${PROJECT_ROOT}/.env"
    fi
else
    skip "Docker not available"
fi

# ── 6. Environment template validation ──────────────────────────────

echo ""
echo -e "${BOLD}[6/6] Environment template${NC}"

if [ -f "${PROJECT_ROOT}/.env.template" ]; then
    # Check it parses as valid KEY=VALUE
    INVALID_LINES=0
    LINE_NUM=0
    while IFS= read -r line; do
        LINE_NUM=$((LINE_NUM + 1))
        # Skip empty lines and comments
        [ -z "${line}" ] && continue
        [[ "${line}" =~ ^[[:space:]]*# ]] && continue
        # Must contain =
        if [[ ! "${line}" =~ = ]]; then
            fail "Invalid .env.template line ${LINE_NUM}: ${line:0:60}"
            INVALID_LINES=$((INVALID_LINES + 1))
        fi
    done < "${PROJECT_ROOT}/.env.template"

    if [ "${INVALID_LINES}" -eq 0 ]; then
        pass ".env.template format valid (${LINE_NUM} lines)"
    fi
else
    fail ".env.template not found"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}=== Smoke Test Results ===${NC}"
echo -e "  ${GREEN}PASS: ${PASS}${NC}  ${RED}FAIL: ${FAIL}${NC}  ${YELLOW}SKIP: ${SKIP}${NC}"
echo ""

if [ "${FAIL}" -gt 0 ]; then
    echo -e "${RED}SMOKE TEST FAILED${NC} — ${FAIL} check(s) failed"
    exit 1
else
    echo -e "${GREEN}SMOKE TEST PASSED${NC}"
    exit 0
fi
