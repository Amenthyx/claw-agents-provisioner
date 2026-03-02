#!/usr/bin/env bash
# ===================================================================
# security-scan.sh — Comprehensive Security Scanning for Claw Agents
# ===================================================================
#
# Runs multiple security scanning tools and produces a SAST summary.
# Exit code 1 on any HIGH or CRITICAL finding.
#
# Tools:
#   1. Bandit       — Python static analysis security testing (SAST)
#   2. ShellCheck   — Bash script security and correctness
#   3. Hadolint     — Dockerfile best practices and security
#   4. pip-audit    — Python dependency vulnerability scanning
#   5. Secret scan  — Check for leaked API keys and credentials
#
# Usage:
#   bash scripts/security-scan.sh           # Full scan
#   bash scripts/security-scan.sh --quick   # Bandit + secrets only
#   bash scripts/security-scan.sh --install # Install tools first
#
# Requirements:
#   pip install bandit pip-audit
#   apt install shellcheck (or brew install shellcheck)
#   docker pull hadolint/hadolint (or brew install hadolint)
# ===================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORT_DIR="${PROJECT_ROOT}/security-reports"

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BLUE='' BOLD='' NC=''
fi

info()    { echo -e "${GREEN}[PASS]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
section() { echo -e "\n${BLUE}${BOLD}=== $* ===${NC}"; }

TOTAL_HIGH=0
TOTAL_FINDINGS=0
QUICK_MODE=false
INSTALL_MODE=false

# ── Parse arguments ──────────────────────────────────────────────────

for arg in "$@"; do
    case "${arg}" in
        --quick)   QUICK_MODE=true ;;
        --install) INSTALL_MODE=true ;;
        --help|-h)
            echo "Usage: $0 [--quick] [--install] [--help]"
            echo "  --quick    Run only Bandit + secret scan"
            echo "  --install  Install required tools first"
            echo "  --help     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown argument: ${arg}"
            exit 1
            ;;
    esac
done

# ── Install mode ─────────────────────────────────────────────────────

if [ "${INSTALL_MODE}" = true ]; then
    section "Installing security tools"
    pip install bandit pip-audit 2>/dev/null || pip install --user bandit pip-audit
    echo ""
    echo "Also recommended (install manually):"
    echo "  shellcheck: sudo apt install shellcheck  (or brew install shellcheck)"
    echo "  hadolint:   docker pull hadolint/hadolint (or brew install hadolint)"
    exit 0
fi

# ── Setup report directory ───────────────────────────────────────────

mkdir -p "${REPORT_DIR}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
SUMMARY_FILE="${REPORT_DIR}/scan-summary-${TIMESTAMP}.txt"

section "Claw Agents Provisioner — Security Scan"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Project:   ${PROJECT_ROOT}"
echo "Mode:      $([ "${QUICK_MODE}" = true ] && echo "quick" || echo "full")"
echo ""

# ── 1. Bandit — Python SAST ─────────────────────────────────────────

section "1. Bandit (Python Security Analysis)"

if command -v bandit &>/dev/null; then
    BANDIT_REPORT="${REPORT_DIR}/bandit-${TIMESTAMP}.json"

    bandit -r "${PROJECT_ROOT}/shared/" \
        -f json \
        -o "${BANDIT_REPORT}" \
        --severity-level medium \
        --confidence-level medium \
        2>/dev/null || true

    if [ -f "${BANDIT_REPORT}" ]; then
        BANDIT_RESULTS=$(python3 -c "
import json, sys
with open('${BANDIT_REPORT}') as f:
    data = json.load(f)
results = data.get('results', [])
high_crit = [r for r in results if r.get('issue_severity') in ('HIGH', 'CRITICAL')]
medium = [r for r in results if r.get('issue_severity') == 'MEDIUM']
low = [r for r in results if r.get('issue_severity') == 'LOW']
print(f'{len(high_crit)}|{len(medium)}|{len(low)}|{len(results)}')
for r in high_crit:
    print(f\"  {r['issue_severity']}/{r['issue_confidence']}: {r['issue_text']}\", file=sys.stderr)
    print(f\"    File: {r['filename']}:{r['line_number']}\", file=sys.stderr)
" 2>&1)

        IFS='|' read -r B_HIGH B_MED B_LOW B_TOTAL <<< "$(echo "${BANDIT_RESULTS}" | head -1)"
        BANDIT_DETAILS=$(echo "${BANDIT_RESULTS}" | tail -n +2)

        if [ "${B_HIGH}" -gt 0 ]; then
            fail "Bandit: ${B_HIGH} HIGH/CRITICAL, ${B_MED} MEDIUM, ${B_LOW} LOW"
            if [ -n "${BANDIT_DETAILS}" ]; then
                echo "${BANDIT_DETAILS}"
            fi
            TOTAL_HIGH=$((TOTAL_HIGH + B_HIGH))
        elif [ "${B_MED}" -gt 0 ]; then
            warn "Bandit: ${B_MED} MEDIUM, ${B_LOW} LOW findings"
        else
            info "Bandit: No significant findings (${B_LOW} LOW)"
        fi
        TOTAL_FINDINGS=$((TOTAL_FINDINGS + B_TOTAL))
    fi
else
    warn "Bandit not installed — skipping (pip install bandit)"
fi

# ── 2. Secret scan — API keys and credentials ───────────────────────

section "2. Secret Scan (API Keys & Credentials)"

SECRET_FOUND=0
SECRET_PATTERNS=(
    "sk-ant-[a-zA-Z0-9]"
    "sk-or-[a-zA-Z0-9]"
    "xoxb-[a-zA-Z0-9]"
    "xapp-[a-zA-Z0-9]"
    "ghp_[a-zA-Z0-9]"
    "gsk_[a-zA-Z0-9]"
    "AKIA[A-Z0-9]{16}"
    "-----BEGIN (RSA |EC )?PRIVATE KEY-----"
)

for pattern in "${SECRET_PATTERNS[@]}"; do
    # Search tracked files only, exclude templates and docs
    MATCHES=$(git -C "${PROJECT_ROOT}" grep -rl "${pattern}" \
        -- ':!.env.template' ':!*.md' ':!*.yml' ':!*.yaml' \
        ':!.pre-commit-config.yaml' ':!scripts/security-scan.sh' \
        2>/dev/null || true)
    if [ -n "${MATCHES}" ]; then
        fail "Found pattern '${pattern}' in:"
        echo "${MATCHES}" | sed 's/^/    /'
        SECRET_FOUND=1
        TOTAL_HIGH=$((TOTAL_HIGH + 1))
    fi
done

if [ "${SECRET_FOUND}" -eq 0 ]; then
    info "No hardcoded secrets or API keys detected"
fi

# ── Quick mode stops here ────────────────────────────────────────────

if [ "${QUICK_MODE}" = true ]; then
    section "Quick Scan Complete"
    echo "HIGH/CRITICAL: ${TOTAL_HIGH}"
    echo "Total findings: ${TOTAL_FINDINGS}"
    exit $([ "${TOTAL_HIGH}" -gt 0 ] && echo 1 || echo 0)
fi

# ── 3. ShellCheck — Bash security ───────────────────────────────────

section "3. ShellCheck (Bash Script Analysis)"

if command -v shellcheck &>/dev/null; then
    SHELL_ISSUES=0
    SHELL_FILES=$(find "${PROJECT_ROOT}" -name "*.sh" -type f 2>/dev/null | grep -v node_modules || true)

    if [ -n "${SHELL_FILES}" ]; then
        for script in ${SHELL_FILES}; do
            RELATIVE=$(echo "${script}" | sed "s|${PROJECT_ROOT}/||")
            if ! shellcheck --severity=warning "${script}" >/dev/null 2>&1; then
                SHELL_ISSUES=$((SHELL_ISSUES + 1))
                warn "ShellCheck issues in: ${RELATIVE}"
            fi
        done

        FILE_COUNT=$(echo "${SHELL_FILES}" | wc -l)
        if [ "${SHELL_ISSUES}" -eq 0 ]; then
            info "ShellCheck: ${FILE_COUNT} scripts checked — no warnings"
        else
            warn "ShellCheck: ${SHELL_ISSUES}/${FILE_COUNT} scripts have warnings"
            TOTAL_FINDINGS=$((TOTAL_FINDINGS + SHELL_ISSUES))
        fi
    else
        info "No shell scripts found"
    fi
else
    warn "ShellCheck not installed — skipping (sudo apt install shellcheck)"
fi

# ── 4. Hadolint — Dockerfile security ───────────────────────────────

section "4. Hadolint (Dockerfile Analysis)"

HADOLINT_CMD=""
if command -v hadolint &>/dev/null; then
    HADOLINT_CMD="hadolint"
elif docker image inspect hadolint/hadolint >/dev/null 2>&1; then
    HADOLINT_CMD="docker run --rm -i hadolint/hadolint"
fi

if [ -n "${HADOLINT_CMD}" ]; then
    DOCKER_ISSUES=0
    DOCKERFILES=$(find "${PROJECT_ROOT}" \( -name "Dockerfile" -o -name "Dockerfile.*" \) -type f 2>/dev/null || true)

    if [ -n "${DOCKERFILES}" ]; then
        for dockerfile in ${DOCKERFILES}; do
            RELATIVE=$(echo "${dockerfile}" | sed "s|${PROJECT_ROOT}/||")
            if ! ${HADOLINT_CMD} --failure-threshold warning "${dockerfile}" >/dev/null 2>&1; then
                DOCKER_ISSUES=$((DOCKER_ISSUES + 1))
                warn "Hadolint issues in: ${RELATIVE}"
            fi
        done

        FILE_COUNT=$(echo "${DOCKERFILES}" | wc -l)
        if [ "${DOCKER_ISSUES}" -eq 0 ]; then
            info "Hadolint: ${FILE_COUNT} Dockerfiles checked — no warnings"
        else
            warn "Hadolint: ${DOCKER_ISSUES}/${FILE_COUNT} Dockerfiles have warnings"
            TOTAL_FINDINGS=$((TOTAL_FINDINGS + DOCKER_ISSUES))
        fi
    else
        info "No Dockerfiles found"
    fi
else
    warn "Hadolint not installed — skipping"
fi

# ── 5. pip-audit — Dependency vulnerability scanning ─────────────────

section "5. pip-audit (Dependency Vulnerabilities)"

if command -v pip-audit &>/dev/null; then
    PIP_AUDIT_REPORT="${REPORT_DIR}/pip-audit-${TIMESTAMP}.json"

    # Scan requirements files if they exist
    REQ_FILES=$(find "${PROJECT_ROOT}" -name "requirements*.txt" -type f 2>/dev/null || true)

    if [ -n "${REQ_FILES}" ]; then
        VULN_COUNT=0
        for req_file in ${REQ_FILES}; do
            RELATIVE=$(echo "${req_file}" | sed "s|${PROJECT_ROOT}/||")
            echo "  Scanning: ${RELATIVE}"
            RESULT=$(pip-audit -r "${req_file}" --format json 2>/dev/null || true)
            if [ -n "${RESULT}" ]; then
                VULNS=$(echo "${RESULT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    deps = data.get('dependencies', [])
    vulns = [d for d in deps if d.get('vulns', [])]
    print(len(vulns))
except:
    print(0)
" 2>/dev/null || echo "0")
                VULN_COUNT=$((VULN_COUNT + VULNS))
            fi
        done

        if [ "${VULN_COUNT}" -gt 0 ]; then
            warn "pip-audit: ${VULN_COUNT} vulnerable dependencies found"
            TOTAL_FINDINGS=$((TOTAL_FINDINGS + VULN_COUNT))
        else
            info "pip-audit: No known vulnerabilities in dependencies"
        fi
    else
        info "No requirements.txt files found — skipping"
    fi
else
    warn "pip-audit not installed — skipping (pip install pip-audit)"
fi

# ── Summary report ───────────────────────────────────────────────────

section "SAST Summary Report"

{
    echo "=== Claw Agents Provisioner — Security Scan Summary ==="
    echo "Timestamp:       $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "HIGH/CRITICAL:   ${TOTAL_HIGH}"
    echo "Total findings:  ${TOTAL_FINDINGS}"
    echo ""
    echo "Tools run:"
    command -v bandit     &>/dev/null && echo "  [x] Bandit" || echo "  [ ] Bandit (not installed)"
    echo "  [x] Secret scan (built-in)"
    command -v shellcheck &>/dev/null && echo "  [x] ShellCheck" || echo "  [ ] ShellCheck (not installed)"
    [ -n "${HADOLINT_CMD:-}" ]        && echo "  [x] Hadolint" || echo "  [ ] Hadolint (not installed)"
    command -v pip-audit  &>/dev/null && echo "  [x] pip-audit" || echo "  [ ] pip-audit (not installed)"
    echo ""
    if [ "${TOTAL_HIGH}" -gt 0 ]; then
        echo "RESULT: FAIL — ${TOTAL_HIGH} HIGH/CRITICAL findings require attention"
    else
        echo "RESULT: PASS — No HIGH/CRITICAL findings"
    fi
} | tee "${SUMMARY_FILE}"

echo ""
info "Full report saved to: ${SUMMARY_FILE}"

if [ -d "${REPORT_DIR}" ]; then
    REPORT_COUNT=$(find "${REPORT_DIR}" -type f | wc -l)
    info "Reports directory: ${REPORT_DIR} (${REPORT_COUNT} files)"
fi

# ── Exit code ────────────────────────────────────────────────────────

if [ "${TOTAL_HIGH}" -gt 0 ]; then
    echo ""
    fail "Exiting with code 1 — HIGH/CRITICAL findings detected"
    exit 1
else
    echo ""
    info "All clear — no HIGH/CRITICAL findings"
    exit 0
fi
