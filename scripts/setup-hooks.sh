#!/usr/bin/env bash
# ===================================================================
# setup-hooks.sh — Install pre-commit hooks for Claw Agents Provisioner
# ===================================================================
# Usage:
#   bash scripts/setup-hooks.sh
#
# Installs pre-commit and configures Git hooks.
# After initial setup, hooks run offline (cached revs).
# ===================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors (safe for non-tty)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' NC=''
fi

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Check prerequisites ──────────────────────────────────────────────

info "Checking prerequisites..."

# Python 3.8+
if ! command -v python3 &>/dev/null; then
    error "python3 is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: ${PYTHON_VERSION}"

# Git
if ! command -v git &>/dev/null; then
    error "git is required but not found"
    exit 1
fi

# Verify we are in a git repo
if ! git -C "${PROJECT_ROOT}" rev-parse --git-dir &>/dev/null; then
    error "Not a git repository: ${PROJECT_ROOT}"
    exit 1
fi

# ── Install pre-commit ───────────────────────────────────────────────

info "Installing pre-commit..."
if command -v pre-commit &>/dev/null; then
    info "pre-commit already installed: $(pre-commit --version)"
else
    pip install pre-commit
    info "pre-commit installed: $(pre-commit --version)"
fi

# ── Install hooks ────────────────────────────────────────────────────

cd "${PROJECT_ROOT}"

info "Installing git hooks from .pre-commit-config.yaml..."
pre-commit install

info "Installing commit-msg hooks..."
pre-commit install --hook-type commit-msg 2>/dev/null || true

# ── Cache hook environments (for offline use) ────────────────────────

info "Caching hook environments (this may take a minute on first run)..."
pre-commit install-hooks

# ── Create secrets baseline if missing ───────────────────────────────

if [ ! -f .secrets.baseline ]; then
    info "Creating detect-secrets baseline..."
    if command -v detect-secrets &>/dev/null; then
        detect-secrets scan \
            --exclude-files '(\.env\.template|\.example\.|package-lock\.json|\.drawio)$' \
            > .secrets.baseline
        info "Baseline created: .secrets.baseline"
    else
        info "Installing detect-secrets for baseline generation..."
        pip install detect-secrets
        detect-secrets scan \
            --exclude-files '(\.env\.template|\.example\.|package-lock\.json|\.drawio)$' \
            > .secrets.baseline
        info "Baseline created: .secrets.baseline"
    fi
fi

# ── Verify installation ─────────────────────────────────────────────

info "Verifying hook installation..."
HOOKS_DIR="${PROJECT_ROOT}/.git/hooks"

if [ -f "${HOOKS_DIR}/pre-commit" ]; then
    info "pre-commit hook installed: ${HOOKS_DIR}/pre-commit"
else
    warn "pre-commit hook file not found — hooks may not trigger"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
info "========================================"
info "  Pre-commit hooks installed"
info "========================================"
echo ""
info "Hooks will run automatically on 'git commit'."
info "Manual run: pre-commit run --all-files"
info "Skip hooks (emergency): git commit --no-verify"
echo ""
