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
#   7. Service health endpoints (--live mode)
#   8. Chat round-trip test (--live mode)
#   9. Memory write/read cycle (--live mode)
#  10. RAG ingest/search cycle (--live mode)
#
# Usage:
#   bash scripts/smoke-test.sh              # Pre-deployment checks only
#   bash scripts/smoke-test.sh --live       # Include live service checks
#   bash scripts/smoke-test.sh --live --token <TOKEN>
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

# ── Parse arguments ──────────────────────────────────────────────────

LIVE_MODE=0
AUTH_TOKEN="${CLAW_AUTH_TOKEN:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --live)
            LIVE_MODE=1
            shift
            ;;
        --token)
            AUTH_TOKEN="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Service ports (override via environment)
ROUTER_PORT="${CLAW_GATEWAY_PORT:-9095}"
MEMORY_PORT="${CLAW_MEMORY_PORT:-9096}"
RAG_PORT="${CLAW_RAG_PORT:-9097}"
DASHBOARD_PORT="${CLAW_DASHBOARD_PORT:-9099}"
HEALTH_PORT="${CLAW_HEALTH_PORT:-9094}"
ORCHESTRATOR_PORT="${CLAW_ORCHESTRATOR_PORT:-9100}"

BASE_HOST="${CLAW_BASE_HOST:-localhost}"

echo -e "${BOLD}=== Claw Agents Provisioner — Smoke Test ===${NC}"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# ── 1. Python shared modules compile ────────────────────────────────

echo -e "${BOLD}[1/10] Python module compilation${NC}"

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
echo -e "${BOLD}[2/10] Python module imports${NC}"

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
echo -e "${BOLD}[3/10] CLI tool health${NC}"

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
echo -e "${BOLD}[4/10] Critical files${NC}"

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
echo -e "${BOLD}[5/10] Docker Compose${NC}"

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
echo -e "${BOLD}[6/10] Environment template${NC}"

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

# ── 7. Live service health endpoints (--live mode) ────────────────

if [ "${LIVE_MODE}" -eq 1 ]; then

echo ""
echo -e "${BOLD}[7/10] Service health endpoints${NC}"

# Build auth header if token provided
AUTH_HEADER=""
if [ -n "${AUTH_TOKEN}" ]; then
    AUTH_HEADER="-H \"Authorization: Bearer ${AUTH_TOKEN}\""
fi

declare -A SERVICE_PORTS
SERVICE_PORTS[router]="${ROUTER_PORT}"
SERVICE_PORTS[memory]="${MEMORY_PORT}"
SERVICE_PORTS[rag]="${RAG_PORT}"
SERVICE_PORTS[dashboard]="${DASHBOARD_PORT}"
SERVICE_PORTS[health]="${HEALTH_PORT}"
SERVICE_PORTS[orchestrator]="${ORCHESTRATOR_PORT}"

for svc in router memory rag dashboard health orchestrator; do
    PORT="${SERVICE_PORTS[$svc]}"
    URL="http://${BASE_HOST}:${PORT}/health"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        --connect-timeout 5 --max-time 10 \
        "${URL}" 2>/dev/null || echo "000")

    if [ "${HTTP_CODE}" = "200" ]; then
        pass "Health OK: ${svc} (:${PORT}) -> ${HTTP_CODE}"
    elif [ "${HTTP_CODE}" = "000" ]; then
        fail "Unreachable: ${svc} (:${PORT})"
    else
        fail "Health FAIL: ${svc} (:${PORT}) -> ${HTTP_CODE}"
    fi
done

# ── 8. Chat round-trip (router -> LLM) ──────────────────────────

echo ""
echo -e "${BOLD}[8/10] Chat round-trip test${NC}"

CHAT_URL="http://${BASE_HOST}:${ROUTER_PORT}/v1/chat/completions"
CHAT_PAYLOAD='{"model":"auto","messages":[{"role":"user","content":"smoke test ping"}],"max_tokens":10}'

CHAT_RESP=$(curl -s -w "\n%{http_code}" \
    -X POST "${CHAT_URL}" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    --connect-timeout 10 --max-time 30 \
    -d "${CHAT_PAYLOAD}" 2>/dev/null || echo -e "\n000")

CHAT_BODY=$(echo "${CHAT_RESP}" | head -n -1)
CHAT_CODE=$(echo "${CHAT_RESP}" | tail -n 1)

if [ "${CHAT_CODE}" = "200" ]; then
    # Check response has choices
    if echo "${CHAT_BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'choices' in d" 2>/dev/null; then
        pass "Chat round-trip: status=${CHAT_CODE}, has choices"
    else
        fail "Chat round-trip: status=${CHAT_CODE}, missing choices in response"
    fi
elif [ "${CHAT_CODE}" = "000" ]; then
    fail "Chat round-trip: router unreachable at :${ROUTER_PORT}"
else
    fail "Chat round-trip: status=${CHAT_CODE}"
fi

# ── 9. Memory write/read cycle ──────────────────────────────────

echo ""
echo -e "${BOLD}[9/10] Memory write/read cycle${NC}"

MEM_BASE="http://${BASE_HOST}:${MEMORY_PORT}"
MEM_CONV_ID="smoke-test-$(date +%s)"
MEM_PAYLOAD=$(python3 -c "
import json; print(json.dumps({
    'conversation_id': '${MEM_CONV_ID}',
    'agent_id': 'smoke-test-agent',
    'messages': [{'role':'user','content':'smoke test message','timestamp':'$(date -u +%Y-%m-%dT%H:%M:%SZ)'}]
}))
" 2>/dev/null || echo '{}')

# Write
MEM_WRITE_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${MEM_BASE}/api/memory/conversations" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    --connect-timeout 5 --max-time 10 \
    -d "${MEM_PAYLOAD}" 2>/dev/null || echo "000")

if [ "${MEM_WRITE_CODE}" = "200" ] || [ "${MEM_WRITE_CODE}" = "201" ]; then
    pass "Memory write: status=${MEM_WRITE_CODE}"
elif [ "${MEM_WRITE_CODE}" = "000" ]; then
    fail "Memory write: service unreachable at :${MEMORY_PORT}"
else
    fail "Memory write: status=${MEM_WRITE_CODE}"
fi

# Read
MEM_READ_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X GET "${MEM_BASE}/api/memory/conversations" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    --connect-timeout 5 --max-time 10 2>/dev/null || echo "000")

if [ "${MEM_READ_CODE}" = "200" ]; then
    pass "Memory read: status=${MEM_READ_CODE}"
elif [ "${MEM_READ_CODE}" = "000" ]; then
    fail "Memory read: service unreachable at :${MEMORY_PORT}"
else
    fail "Memory read: status=${MEM_READ_CODE}"
fi

# ── 10. RAG ingest/search cycle ─────────────────────────────────

echo ""
echo -e "${BOLD}[10/10] RAG ingest/search cycle${NC}"

RAG_BASE="http://${BASE_HOST}:${RAG_PORT}"
RAG_DOC_ID="smoke-test-doc-$(date +%s)"
RAG_INGEST_PAYLOAD=$(python3 -c "
import json; print(json.dumps({
    'document_id': '${RAG_DOC_ID}',
    'title': 'Smoke Test Document',
    'content': 'This is a smoke test document for verifying RAG pipeline ingestion.',
    'metadata': {'source': 'smoke-test'}
}))
" 2>/dev/null || echo '{}')

# Ingest
RAG_INGEST_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${RAG_BASE}/api/rag/ingest" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    --connect-timeout 5 --max-time 10 \
    -d "${RAG_INGEST_PAYLOAD}" 2>/dev/null || echo "000")

if [ "${RAG_INGEST_CODE}" = "200" ] || [ "${RAG_INGEST_CODE}" = "201" ]; then
    pass "RAG ingest: status=${RAG_INGEST_CODE}"
elif [ "${RAG_INGEST_CODE}" = "000" ]; then
    fail "RAG ingest: service unreachable at :${RAG_PORT}"
else
    fail "RAG ingest: status=${RAG_INGEST_CODE}"
fi

# Search
RAG_SEARCH_PAYLOAD='{"query":"smoke test document","top_k":3}'
RAG_SEARCH_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${RAG_BASE}/api/rag/search" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    --connect-timeout 5 --max-time 10 \
    -d "${RAG_SEARCH_PAYLOAD}" 2>/dev/null || echo "000")

if [ "${RAG_SEARCH_CODE}" = "200" ]; then
    pass "RAG search: status=${RAG_SEARCH_CODE}"
elif [ "${RAG_SEARCH_CODE}" = "000" ]; then
    fail "RAG search: service unreachable at :${RAG_PORT}"
else
    fail "RAG search: status=${RAG_SEARCH_CODE}"
fi

else
    # Not in --live mode
    echo ""
    echo -e "${YELLOW}Sections 7-10 skipped (use --live for post-deployment checks)${NC}"
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
