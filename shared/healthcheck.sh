#!/usr/bin/env bash
# ===================================================================
# CLAW AGENTS PROVISIONER — Unified Health Check
# ===================================================================
# Runs the appropriate health check for a given Claw agent and outputs
# structured pass/fail results.
#
# Usage:
#   ./shared/healthcheck.sh <agent>
#   ./shared/healthcheck.sh zeroclaw
#   ./shared/healthcheck.sh nanoclaw
#   ./shared/healthcheck.sh picoclaw
#   ./shared/healthcheck.sh openclaw
#   ./shared/healthcheck.sh all         # Check all agents
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed
#   2 = invalid arguments
# ===================================================================
set -euo pipefail

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HEALTHCHECK_TIMEOUT=30  # seconds

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
log_pass() {
    echo -e "\033[1;32m[PASS]\033[0m $*"
}

log_fail() {
    echo -e "\033[1;31m[FAIL]\033[0m $*"
}

log_skip() {
    echo -e "\033[1;33m[SKIP]\033[0m $*"
}

log_info() {
    echo -e "\033[1;34m[INFO]\033[0m $*"
}

print_usage() {
    echo "Usage: $0 <agent>"
    echo ""
    echo "Agents:"
    echo "  zeroclaw   — Run ZeroClaw health check (zeroclaw doctor)"
    echo "  nanoclaw   — Run NanoClaw health check (container status)"
    echo "  picoclaw   — Run PicoClaw health check (picoclaw agent -m ping)"
    echo "  openclaw   — Run OpenClaw health check (openclaw doctor)"
    echo "  all        — Run health checks for all agents"
    echo ""
    echo "Exit codes:"
    echo "  0 = all checks passed"
    echo "  1 = one or more checks failed"
    echo "  2 = invalid arguments"
}

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# -------------------------------------------------------------------
# Health check functions — one per agent
# -------------------------------------------------------------------

check_zeroclaw() {
    log_info "Checking ZeroClaw..."
    local status="fail"
    local details=""

    # Check 1: Binary exists
    if command -v zeroclaw > /dev/null 2>&1; then
        details="binary found"
    else
        log_fail "ZeroClaw: binary not found in PATH"
        echo "  {\"agent\": \"zeroclaw\", \"status\": \"fail\", \"reason\": \"binary not found\", \"timestamp\": \"$(timestamp)\"}"
        return 1
    fi

    # Check 2: Run zeroclaw doctor
    if timeout "${HEALTHCHECK_TIMEOUT}" zeroclaw doctor > /dev/null 2>&1; then
        status="pass"
        details="zeroclaw doctor passed"
        log_pass "ZeroClaw: ${details}"
    else
        details="zeroclaw doctor failed or timed out"
        log_fail "ZeroClaw: ${details}"
    fi

    echo "  {\"agent\": \"zeroclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
    [[ "$status" == "pass" ]]
}

check_nanoclaw() {
    log_info "Checking NanoClaw..."
    local status="fail"
    local details=""

    # NanoClaw has no CLI doctor command — check Docker container status
    # Look for a running container with "nanoclaw" in the name
    if command -v docker > /dev/null 2>&1; then
        local container_status
        container_status=$(docker ps --filter "name=nanoclaw" --format "{{.Status}}" 2>/dev/null || echo "")

        if [[ -n "$container_status" ]]; then
            if echo "$container_status" | grep -qi "up"; then
                status="pass"
                details="container running: ${container_status}"
                log_pass "NanoClaw: ${details}"
            else
                details="container exists but not running: ${container_status}"
                log_fail "NanoClaw: ${details}"
            fi
        else
            # Fallback: check if nanoclaw process is running natively
            if pgrep -f "nanoclaw" > /dev/null 2>&1; then
                status="pass"
                details="process running (native)"
                log_pass "NanoClaw: ${details}"
            else
                details="no container or process found"
                log_fail "NanoClaw: ${details}"
            fi
        fi
    else
        # Docker not available — check for native process
        if pgrep -f "nanoclaw" > /dev/null 2>&1; then
            status="pass"
            details="process running (native, no Docker)"
            log_pass "NanoClaw: ${details}"
        else
            details="Docker not available and no native process found"
            log_fail "NanoClaw: ${details}"
        fi
    fi

    echo "  {\"agent\": \"nanoclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
    [[ "$status" == "pass" ]]
}

check_picoclaw() {
    log_info "Checking PicoClaw..."
    local status="fail"
    local details=""

    # Check 1: Binary exists
    if command -v picoclaw > /dev/null 2>&1; then
        details="binary found"
    else
        # Check if running in Docker
        local container_status
        container_status=$(docker ps --filter "name=picoclaw" --format "{{.Status}}" 2>/dev/null || echo "")
        if [[ -n "$container_status" ]] && echo "$container_status" | grep -qi "up"; then
            status="pass"
            details="container running: ${container_status}"
            log_pass "PicoClaw: ${details}"
            echo "  {\"agent\": \"picoclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
            return 0
        fi

        log_fail "PicoClaw: binary not found in PATH and no container running"
        echo "  {\"agent\": \"picoclaw\", \"status\": \"fail\", \"reason\": \"binary not found\", \"timestamp\": \"$(timestamp)\"}"
        return 1
    fi

    # Check 2: Run picoclaw agent with a ping message
    if timeout "${HEALTHCHECK_TIMEOUT}" picoclaw agent -m "ping" > /dev/null 2>&1; then
        status="pass"
        details="picoclaw agent ping succeeded"
        log_pass "PicoClaw: ${details}"
    else
        details="picoclaw agent ping failed or timed out"
        log_fail "PicoClaw: ${details}"
    fi

    echo "  {\"agent\": \"picoclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
    [[ "$status" == "pass" ]]
}

check_openclaw() {
    log_info "Checking OpenClaw..."
    local status="fail"
    local details=""

    # Check 1: Binary / npx command exists
    if command -v openclaw > /dev/null 2>&1; then
        details="binary found"
    else
        # Check if running in Docker
        local container_status
        container_status=$(docker ps --filter "name=openclaw" --format "{{.Status}}" 2>/dev/null || echo "")
        if [[ -n "$container_status" ]] && echo "$container_status" | grep -qi "up"; then
            status="pass"
            details="container running: ${container_status}"
            log_pass "OpenClaw: ${details}"
            echo "  {\"agent\": \"openclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
            return 0
        fi

        log_fail "OpenClaw: binary not found in PATH and no container running"
        echo "  {\"agent\": \"openclaw\", \"status\": \"fail\", \"reason\": \"binary not found\", \"timestamp\": \"$(timestamp)\"}"
        return 1
    fi

    # Check 2: Run openclaw doctor
    if timeout "${HEALTHCHECK_TIMEOUT}" openclaw doctor > /dev/null 2>&1; then
        status="pass"
        details="openclaw doctor passed"
        log_pass "OpenClaw: ${details}"
    else
        details="openclaw doctor failed or timed out"
        log_fail "OpenClaw: ${details}"
    fi

    echo "  {\"agent\": \"openclaw\", \"status\": \"${status}\", \"details\": \"${details}\", \"timestamp\": \"$(timestamp)\"}"
    [[ "$status" == "pass" ]]
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    print_usage
    exit 2
fi

AGENT="${1,,}"  # Lowercase
OVERALL_STATUS=0

echo ""
log_info "========================================="
log_info "  Claw Agents — Health Check"
log_info "  $(timestamp)"
log_info "========================================="
echo ""

case "$AGENT" in
    zeroclaw)
        check_zeroclaw || OVERALL_STATUS=1
        ;;
    nanoclaw)
        check_nanoclaw || OVERALL_STATUS=1
        ;;
    picoclaw)
        check_picoclaw || OVERALL_STATUS=1
        ;;
    openclaw)
        check_openclaw || OVERALL_STATUS=1
        ;;
    all)
        echo "{"
        echo "  \"healthcheck\": ["
        check_zeroclaw || OVERALL_STATUS=1
        echo ","
        check_nanoclaw || OVERALL_STATUS=1
        echo ","
        check_picoclaw || OVERALL_STATUS=1
        echo ","
        check_openclaw || OVERALL_STATUS=1
        echo ""
        echo "  ],"
        echo "  \"overall\": \"$( [[ $OVERALL_STATUS -eq 0 ]] && echo 'pass' || echo 'fail' )\","
        echo "  \"timestamp\": \"$(timestamp)\""
        echo "}"
        ;;
    -h|--help|help)
        print_usage
        exit 0
        ;;
    *)
        log_fail "Unknown agent: ${AGENT}"
        print_usage
        exit 2
        ;;
esac

echo ""
if [[ $OVERALL_STATUS -eq 0 ]]; then
    log_pass "Health check completed — all checks passed."
else
    log_fail "Health check completed — one or more checks failed."
fi

exit $OVERALL_STATUS
