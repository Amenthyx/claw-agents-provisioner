#!/usr/bin/env bash
# ===================================================================
# run-load-tests.sh -- Run All k6 Load Tests Sequentially
# ===================================================================
#
# Executes each k6 load test in order, captures JSON output for
# post-processing, and generates a summary report.
#
# Prerequisites:
#   - k6 installed (https://k6.io/docs/get-started/installation/)
#   - All Claw services running (or use --dry-run for validation)
#
# Usage:
#   bash tests/load/run-load-tests.sh                      # Run all
#   bash tests/load/run-load-tests.sh --service router     # Run one
#   bash tests/load/run-load-tests.sh --dry-run             # Validate only
#
# Environment:
#   K6_AUTH_TOKEN     -- Bearer token for service auth
#   K6_BASE_HOST      -- Hostname (default: localhost)
#   K6_ROUTER_PORT    -- Router port override (default: 9095)
#   K6_MEMORY_PORT    -- Memory port override (default: 9096)
#   K6_RAG_PORT       -- RAG port override (default: 9097)
#   K6_DASHBOARD_PORT -- Dashboard port override (default: 9099)
# ===================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RESULTS_DIR="${PROJECT_ROOT}/tests/load/results"

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
fi

# ── Parse arguments ──────────────────────────────────────────────────

DRY_RUN=0
SERVICE_FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --service)
            SERVICE_FILTER="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: bash tests/load/run-load-tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --service NAME   Run only the specified service test"
            echo "                   (router, memory, rag, dashboard)"
            echo "  --dry-run        Validate k6 scripts without running"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# ── Preflight checks ────────────────────────────────────────────────

echo -e "${BOLD}=== Claw Agents — k6 Load Test Suite ===${NC}"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Check k6 is installed
if ! command -v k6 &>/dev/null; then
    echo -e "${RED}ERROR: k6 is not installed.${NC}"
    echo "Install: https://k6.io/docs/get-started/installation/"
    echo "  macOS: brew install k6"
    echo "  Linux: sudo gpg -k; sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68; echo 'deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list; sudo apt-get update; sudo apt-get install k6"
    echo "  Docker: docker run --rm -i grafana/k6 run -"
    exit 1
fi

echo -e "${GREEN}k6 found:${NC} $(k6 version 2>/dev/null || echo 'version unknown')"
echo ""

# Create results directory
mkdir -p "${RESULTS_DIR}"

# ── Test definitions ─────────────────────────────────────────────────

declare -A TESTS
TESTS[router]="k6-router.js"
TESTS[memory]="k6-memory.js"
TESTS[rag]="k6-rag.js"
TESTS[dashboard]="k6-dashboard.js"

TEST_ORDER=("router" "memory" "rag" "dashboard")

# ── Execution ────────────────────────────────────────────────────────

PASS=0
FAIL=0
SKIP=0
TOTAL_START=$(date +%s)

for service in "${TEST_ORDER[@]}"; do
    # Apply service filter if specified
    if [ -n "${SERVICE_FILTER}" ] && [ "${SERVICE_FILTER}" != "${service}" ]; then
        continue
    fi

    SCRIPT="${SCRIPT_DIR}/${TESTS[$service]}"
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    JSON_OUT="${RESULTS_DIR}/${service}_${TIMESTAMP}.json"
    SUMMARY_OUT="${RESULTS_DIR}/${service}_${TIMESTAMP}_summary.txt"

    echo -e "${BOLD}────────────────────────────────────────${NC}"
    echo -e "${CYAN}Testing: ${service}${NC} (${TESTS[$service]})"
    echo ""

    if [ ! -f "${SCRIPT}" ]; then
        echo -e "${RED}  SKIP: Script not found: ${SCRIPT}${NC}"
        SKIP=$((SKIP + 1))
        continue
    fi

    if [ "${DRY_RUN}" -eq 1 ]; then
        echo -e "${YELLOW}  DRY-RUN: Validating script syntax...${NC}"
        # k6 inspect validates the script without running it
        if k6 inspect "${SCRIPT}" >/dev/null 2>&1; then
            echo -e "${GREEN}  VALID: ${TESTS[$service]}${NC}"
            PASS=$((PASS + 1))
        else
            echo -e "${RED}  INVALID: ${TESTS[$service]}${NC}"
            k6 inspect "${SCRIPT}" 2>&1 | head -20
            FAIL=$((FAIL + 1))
        fi
        continue
    fi

    # Run k6 with JSON output
    SERVICE_START=$(date +%s)
    echo -e "  Output: ${JSON_OUT}"
    echo ""

    if k6 run \
        --out "json=${JSON_OUT}" \
        --summary-export="${SUMMARY_OUT}" \
        --env "K6_AUTH_TOKEN=${K6_AUTH_TOKEN:-test-token}" \
        --env "K6_BASE_HOST=${K6_BASE_HOST:-localhost}" \
        "${SCRIPT}" 2>&1; then

        SERVICE_END=$(date +%s)
        DURATION=$((SERVICE_END - SERVICE_START))
        echo ""
        echo -e "${GREEN}  PASS: ${service} (${DURATION}s)${NC}"
        PASS=$((PASS + 1))
    else
        SERVICE_END=$(date +%s)
        DURATION=$((SERVICE_END - SERVICE_START))
        echo ""
        echo -e "${RED}  FAIL: ${service} (${DURATION}s)${NC}"
        FAIL=$((FAIL + 1))
    fi

    echo ""
done

# ── Summary ──────────────────────────────────────────────────────────

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

echo -e "${BOLD}=== Load Test Results ===${NC}"
echo -e "  ${GREEN}PASS: ${PASS}${NC}  ${RED}FAIL: ${FAIL}${NC}  ${YELLOW}SKIP: ${SKIP}${NC}"
echo -e "  Total duration: ${TOTAL_DURATION}s"
echo -e "  Results dir: ${RESULTS_DIR}"
echo ""

if [ "${FAIL}" -gt 0 ]; then
    echo -e "${RED}LOAD TESTS FAILED${NC} -- ${FAIL} service(s) did not meet thresholds"
    exit 1
else
    echo -e "${GREEN}ALL LOAD TESTS PASSED${NC}"
    exit 0
fi
