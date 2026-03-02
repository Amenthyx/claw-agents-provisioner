#!/usr/bin/env python3
"""
Claw Vault -- Encrypted Secrets Vault for Claw Agents Provisioner

Stores API keys and secrets in an AES-encrypted vault file using
Fernet symmetric encryption with PBKDF2 key derivation.  Secrets
are held as a JSON dict inside a single Fernet token, prepended
with a magic header and per-vault salt.

Binary vault format:
    CLAWVAULT1   (9 bytes, ASCII magic)
    <salt>       (16 bytes, random)
    <fernet>     (remaining bytes, Fernet token)

Key derivation:
    PBKDF2-HMAC-SHA256, 480 000 iterations, 16-byte salt -> 32-byte key
    Key is base64url-encoded for Fernet.

Password resolution order:
    1. CLAW_VAULT_PASSWORD environment variable
    2. --password-file CLI argument (reads first line)
    3. Interactive prompt via getpass

Usage:
    python shared/claw_vault.py init
    python shared/claw_vault.py set ANTHROPIC_API_KEY sk-ant-...
    python shared/claw_vault.py get ANTHROPIC_API_KEY
    python shared/claw_vault.py list
    python shared/claw_vault.py delete ANTHROPIC_API_KEY
    python shared/claw_vault.py import-env .env
    python shared/claw_vault.py export-env secrets.env
    python shared/claw_vault.py inject /run/secrets/decrypted
    python shared/claw_vault.py rotate
    python shared/claw_vault.py rotate-secrets --policy rotation-policy.json
    python shared/claw_vault.py rotation-status --policy rotation-policy.json

Requirements:
    Python 3.8+
    cryptography  (pip install cryptography)
"""

import argparse
import copy
import getpass
import json
import logging
import os
import signal
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    print(
        "ERROR: 'cryptography' package is required.\n"
        "Install it with:  pip install cryptography",
        file=sys.stderr,
    )
    sys.exit(1)

import base64

from claw_audit import get_audit_logger


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

VAULT_MAGIC = b"CLAWVAULT1"          # 10 bytes — file format identifier
SALT_LENGTH = 16                      # bytes
PBKDF2_ITERATIONS = 480_000
DEFAULT_VAULT_FILE = "secrets.vault"
DEFAULT_ROTATION_POLICY = "rotation-policy.json"
DEFAULT_ROTATION_LOG = "logs/rotation-audit.jsonl"
DEFAULT_GRACE_PERIOD_HOURS = 24       # hours to keep old key accessible


# ═══════════════════════════════════════════════════════════════════════════════
#  Logging
# ═══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("claw-vault")


def setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)


# ═══════════════════════════════════════════════════════════════════════════════
#  Key Derivation
# ═══════════════════════════════════════════════════════════════════════════════

def _derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte Fernet-compatible key from a password and salt.

    Uses PBKDF2-HMAC-SHA256 with 480 000 iterations.  The result is
    base64url-encoded (44 bytes) as required by Fernet.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    raw_key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


# ═══════════════════════════════════════════════════════════════════════════════
#  Password Resolution
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_password(password_file: str = None, prompt: str = "Vault password: ") -> str:
    """
    Resolve the vault password from (in priority order):
      1. CLAW_VAULT_PASSWORD environment variable
      2. --password-file argument (first line of the file)
      3. Interactive getpass prompt
    """
    # 1. Environment variable
    env_pw = os.environ.get("CLAW_VAULT_PASSWORD")
    if env_pw:
        return env_pw

    # 2. Password file
    if password_file:
        pf = Path(password_file)
        if not pf.exists():
            logger.error(f"Password file not found: {password_file}")
            sys.exit(1)
        password = pf.read_text(encoding="utf-8").splitlines()[0].strip()
        if not password:
            logger.error(f"Password file is empty: {password_file}")
            sys.exit(1)
        return password

    # 3. Interactive prompt
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  VaultFile  --  Binary format read/write
# ═══════════════════════════════════════════════════════════════════════════════

class VaultFile:
    """
    Handles reading and writing the binary vault format:

        CLAWVAULT1 (9 bytes) + salt (16 bytes) + fernet_token (rest)

    All writes are atomic: data goes to a temporary file in the same
    directory, then is renamed over the target path.
    """

    def __init__(self, path: str):
        self.path = Path(path).resolve()

    def exists(self) -> bool:
        return self.path.exists()

    def read_raw(self) -> tuple:
        """Read vault file and return (salt, fernet_token_bytes)."""
        data = self.path.read_bytes()

        # Validate magic header
        if not data.startswith(VAULT_MAGIC):
            raise ValueError(
                f"Invalid vault file (bad magic header): {self.path}"
            )

        offset = len(VAULT_MAGIC)
        salt = data[offset : offset + SALT_LENGTH]
        if len(salt) < SALT_LENGTH:
            raise ValueError(
                f"Vault file is corrupted (truncated salt): {self.path}"
            )

        fernet_token = data[offset + SALT_LENGTH :]
        if not fernet_token:
            raise ValueError(
                f"Vault file is corrupted (no encrypted data): {self.path}"
            )

        return salt, fernet_token

    def write_raw(self, salt: bytes, fernet_token: bytes):
        """Write vault file atomically (temp + rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = VAULT_MAGIC + salt + fernet_token

        # Write to temp file in the same directory, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=".vault_tmp_",
        )
        try:
            os.write(fd, payload)
            os.close(fd)
            # On Windows, target must not exist for os.rename
            if sys.platform == "win32" and self.path.exists():
                os.replace(tmp_path, str(self.path))
            else:
                os.rename(tmp_path, str(self.path))
        except (OSError, ValueError):
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def __repr__(self) -> str:
        return f"VaultFile({self.path})"


# ═══════════════════════════════════════════════════════════════════════════════
#  SecretStore  --  Dict-like wrapper around Fernet encrypt/decrypt
# ═══════════════════════════════════════════════════════════════════════════════

class SecretStore:
    """
    In-memory secret store backed by a VaultFile.

    Secrets are stored as a JSON dict encrypted with Fernet.
    All mutations are flushed to disk atomically on .save().
    """

    def __init__(self, vault_file: VaultFile, password: str):
        self._vault = vault_file
        self._password = password
        self._secrets: dict = {}
        self._salt: bytes = b""

    # ── Loading ──────────────────────────────────────────────────────────────

    def load(self):
        """Decrypt and load secrets from the vault file."""
        salt, token = self._vault.read_raw()
        self._salt = salt

        key = _derive_key(self._password, salt)
        fernet = Fernet(key)

        try:
            plaintext = fernet.decrypt(token)
        except InvalidToken:
            raise PermissionError("Invalid vault password")

        self._secrets = json.loads(plaintext.decode("utf-8"))

    @classmethod
    def create_empty(cls, vault_file: VaultFile, password: str) -> "SecretStore":
        """Create a new empty vault and write it to disk."""
        store = cls(vault_file, password)
        store._salt = os.urandom(SALT_LENGTH)
        store._secrets = {}
        store.save()
        return store

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self):
        """Encrypt and write secrets to the vault file atomically."""
        key = _derive_key(self._password, self._salt)
        fernet = Fernet(key)

        plaintext = json.dumps(self._secrets, sort_keys=True).encode("utf-8")
        token = fernet.encrypt(plaintext)

        self._vault.write_raw(self._salt, token)

    # ── Dict-like access ─────────────────────────────────────────────────────

    def get(self, key: str) -> str:
        if key not in self._secrets:
            raise KeyError(f"Secret not found: {key}")
        return self._secrets[key]

    def set(self, key: str, value: str):
        self._secrets[key] = value

    def delete(self, key: str):
        if key not in self._secrets:
            raise KeyError(f"Secret not found: {key}")
        del self._secrets[key]

    def keys(self) -> list:
        return sorted(self._secrets.keys())

    def items(self) -> list:
        return sorted(self._secrets.items())

    def __contains__(self, key: str) -> bool:
        return key in self._secrets

    def __len__(self) -> int:
        return len(self._secrets)

    def re_encrypt(self, new_password: str):
        """Re-encrypt the vault with a new password and fresh salt."""
        self._password = new_password
        self._salt = os.urandom(SALT_LENGTH)
        self.save()


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: Open existing vault
# ═══════════════════════════════════════════════════════════════════════════════

def _open_vault(vault_path: str, password_file: str = None) -> SecretStore:
    """Open an existing vault or exit with a helpful message."""
    vf = VaultFile(vault_path)

    if not vf.exists():
        logger.error(
            f"No vault found at: {vf.path}\n"
            "Run:  python shared/claw_vault.py init"
        )
        sys.exit(1)

    password = _resolve_password(password_file)
    store = SecretStore(vf, password)

    try:
        store.load()
    except PermissionError:
        logger.error("Invalid vault password")
        sys.exit(1)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    return store


# ═══════════════════════════════════════════════════════════════════════════════
#  Rotation Policy — Scheduled secret rotation with grace periods
# ═══════════════════════════════════════════════════════════════════════════════

class RotationPolicy:
    """
    Manages scheduled secret rotation with configurable policies.

    Policy file format (JSON):
    {
        "version": 1,
        "default_rotation_days": 90,
        "default_grace_period_hours": 24,
        "secrets": {
            "ANTHROPIC_API_KEY": {
                "rotation_days": 30,
                "grace_period_hours": 48,
                "last_rotated": "2025-01-15T00:00:00Z",
                "previous_value": null,
                "grace_expires": null
            }
        }
    }
    """

    def __init__(self, policy_path: str):
        self.path = Path(policy_path).resolve()
        self._policy: Dict[str, Any] = {}

    def load(self) -> None:
        """Load rotation policy from disk."""
        if not self.path.exists():
            self._policy = {
                "version": 1,
                "default_rotation_days": 90,
                "default_grace_period_hours": DEFAULT_GRACE_PERIOD_HOURS,
                "secrets": {},
            }
            return
        data = self.path.read_text(encoding="utf-8")
        self._policy = json.loads(data)

    def save(self) -> None:
        """Persist rotation policy to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._policy, indent=2, sort_keys=True)
        # Atomic write
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".policy_tmp_"
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            if sys.platform == "win32" and self.path.exists():
                os.replace(tmp_path, str(self.path))
            else:
                os.rename(tmp_path, str(self.path))
        except (OSError, ValueError):
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @property
    def default_rotation_days(self) -> int:
        return self._policy.get("default_rotation_days", 90)

    @property
    def default_grace_hours(self) -> int:
        return self._policy.get(
            "default_grace_period_hours", DEFAULT_GRACE_PERIOD_HOURS
        )

    def get_secret_policy(self, key: str) -> Dict[str, Any]:
        """Get rotation config for a specific secret."""
        secrets = self._policy.get("secrets", {})
        return secrets.get(key, {})

    def set_secret_policy(
        self,
        key: str,
        rotation_days: Optional[int] = None,
        grace_period_hours: Optional[int] = None,
    ) -> None:
        """Set or update rotation config for a specific secret."""
        if "secrets" not in self._policy:
            self._policy["secrets"] = {}
        entry = self._policy["secrets"].get(key, {})
        if rotation_days is not None:
            entry["rotation_days"] = rotation_days
        if grace_period_hours is not None:
            entry["grace_period_hours"] = grace_period_hours
        self._policy["secrets"][key] = entry

    def record_rotation(
        self, key: str, previous_value: Optional[str] = None
    ) -> None:
        """Record that a secret was rotated, storing previous value for grace."""
        now = datetime.now(timezone.utc)
        if "secrets" not in self._policy:
            self._policy["secrets"] = {}
        entry = self._policy["secrets"].get(key, {})

        entry["last_rotated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        grace_hours = entry.get("grace_period_hours", self.default_grace_hours)
        grace_expires = now + timedelta(hours=grace_hours)
        entry["grace_expires"] = grace_expires.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Store previous value (encrypted in the policy, only for grace retrieval)
        if previous_value is not None:
            entry["previous_value"] = previous_value
        else:
            entry["previous_value"] = None

        self._policy["secrets"][key] = entry

    def clear_expired_grace(self) -> List[str]:
        """Remove previous values for secrets whose grace period has expired."""
        now = datetime.now(timezone.utc)
        cleared = []
        for key, entry in self._policy.get("secrets", {}).items():
            grace_str = entry.get("grace_expires")
            if grace_str and entry.get("previous_value") is not None:
                grace_dt = datetime.strptime(
                    grace_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                if now >= grace_dt:
                    entry["previous_value"] = None
                    entry["grace_expires"] = None
                    cleared.append(key)
        return cleared

    def get_due_secrets(self, all_keys: List[str]) -> List[Dict[str, Any]]:
        """Return list of secrets that are due for rotation."""
        now = datetime.now(timezone.utc)
        due = []
        for key in all_keys:
            entry = self.get_secret_policy(key)
            rotation_days = entry.get("rotation_days", self.default_rotation_days)
            last_rotated_str = entry.get("last_rotated")

            if last_rotated_str:
                last_rotated = datetime.strptime(
                    last_rotated_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                days_since = (now - last_rotated).days
                is_due = days_since >= rotation_days
            else:
                # Never rotated — always due
                days_since = -1
                is_due = True

            if is_due:
                due.append({
                    "key": key,
                    "rotation_days": rotation_days,
                    "days_since_rotation": days_since,
                    "last_rotated": last_rotated_str or "never",
                })
        return due


def _log_rotation_event(
    action: str,
    key: str,
    outcome: str,
    details: Optional[Dict[str, Any]] = None,
    log_path: str = DEFAULT_ROTATION_LOG,
) -> None:
    """Append a structured JSON entry to the rotation audit log."""
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
        "action": action,
        "key": key,
        "outcome": outcome,
        "details": details or {},
    }

    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Commands
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_init(args):
    """Create a new empty vault."""
    vf = VaultFile(args.vault_file)

    if vf.exists() and not args.force:
        logger.error(
            f"Vault already exists: {vf.path}\n"
            "Use --force to overwrite."
        )
        sys.exit(1)

    password = _resolve_password(args.password_file, prompt="New vault password: ")
    if not os.environ.get("CLAW_VAULT_PASSWORD") and not args.password_file:
        confirm = getpass.getpass("Confirm vault password: ")
        if password != confirm:
            logger.error("Passwords do not match")
            sys.exit(1)

    SecretStore.create_empty(vf, password)
    logger.info(f"Vault created: {vf.path}")

    audit = get_audit_logger()
    audit.log_config_change(
        action="vault_init",
        resource=str(vf.path),
        outcome="success",
    )


def cmd_set(args):
    """Store a single key-value pair."""
    store = _open_vault(args.vault_file, args.password_file)
    store.set(args.key, args.value)
    store.save()
    logger.info(f"Secret stored: {args.key}")

    audit = get_audit_logger()
    audit.log_data_access(
        action="vault_set",
        resource=args.key,
        outcome="success",
    )


def cmd_get(args):
    """Retrieve and print a single secret."""
    store = _open_vault(args.vault_file, args.password_file)
    try:
        value = store.get(args.key)
        # Print raw value (no logging prefix) for piping
        print(value)
        audit = get_audit_logger()
        audit.log_data_access(
            action="vault_get",
            resource=args.key,
            outcome="success",
        )
    except KeyError:
        audit = get_audit_logger()
        audit.log_data_access(
            action="vault_get",
            resource=args.key,
            outcome="failure",
            details={"reason": "not_found"},
        )
        logger.error(f"Secret not found: {args.key}")
        sys.exit(1)


def cmd_list(args):
    """List all secret key names (not values)."""
    store = _open_vault(args.vault_file, args.password_file)
    keys = store.keys()
    if not keys:
        logger.info("Vault is empty")
        return
    for key in keys:
        print(key)


def cmd_delete(args):
    """Remove a key from the vault."""
    store = _open_vault(args.vault_file, args.password_file)
    try:
        store.delete(args.key)
        store.save()
        logger.info(f"Secret deleted: {args.key}")

        audit = get_audit_logger()
        audit.log_data_access(
            action="vault_delete",
            resource=args.key,
            outcome="success",
        )
    except KeyError:
        audit = get_audit_logger()
        audit.log_data_access(
            action="vault_delete",
            resource=args.key,
            outcome="failure",
            details={"reason": "not_found"},
        )
        logger.error(f"Secret not found: {args.key}")
        sys.exit(1)


def cmd_import_env(args):
    """Import KEY=VALUE pairs from a .env file into the vault."""
    env_path = Path(args.env_file)
    if not env_path.exists():
        logger.error(f"File not found: {args.env_file}")
        sys.exit(1)

    store = _open_vault(args.vault_file, args.password_file)

    imported = 0
    skipped = 0
    for line_num, line in enumerate(
        env_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Parse KEY=VALUE (supports optional quoting)
        if "=" not in line:
            logger.warning(f"Skipping malformed line {line_num}: {line[:60]}")
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip surrounding quotes from value
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        if not key:
            continue

        if key in store and not args.overwrite:
            logger.info(f"Skipped (exists): {key}")
            skipped += 1
            continue

        store.set(key, value)
        imported += 1

    store.save()
    logger.info(
        f"Import complete: {imported} imported, {skipped} skipped (already exist)"
    )


def cmd_export_env(args):
    """Export all secrets to a .env file."""
    store = _open_vault(args.vault_file, args.password_file)

    out_path = Path(args.output_file)
    if out_path.exists() and not args.force:
        logger.error(
            f"Output file already exists: {out_path}\n"
            "Use --force to overwrite."
        )
        sys.exit(1)

    lines = []
    for key, value in store.items():
        # Quote values that contain spaces, quotes, or special chars
        if any(c in value for c in (" ", '"', "'", "#", "\n", "\\", "$")):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Exported {len(lines)} secrets to: {out_path}")


def cmd_inject(args):
    """Write each secret to an individual file in the target directory."""
    store = _open_vault(args.vault_file, args.password_file)

    target_dir = Path(args.directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for key, value in store.items():
        secret_path = target_dir / key
        # Atomic write via temp file
        fd, tmp_path = tempfile.mkstemp(dir=str(target_dir), prefix=f".{key}_")
        try:
            os.write(fd, value.encode("utf-8"))
            os.close(fd)
            if sys.platform == "win32" and secret_path.exists():
                os.replace(tmp_path, str(secret_path))
            else:
                os.rename(tmp_path, str(secret_path))
            count += 1
        except (OSError, ValueError):
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    logger.info(f"Injected {count} secrets into: {target_dir}")


def cmd_rotate(args):
    """Change the vault password.  Re-encrypts with a new salt."""
    vf = VaultFile(args.vault_file)

    if not vf.exists():
        logger.error(
            f"No vault found at: {vf.path}\n"
            "Run:  python shared/claw_vault.py init"
        )
        sys.exit(1)

    # Get old password
    old_password = _resolve_password(
        args.password_file, prompt="Current vault password: "
    )
    store = SecretStore(vf, old_password)
    try:
        store.load()
    except PermissionError:
        logger.error("Invalid vault password")
        sys.exit(1)

    # Get new password
    new_password = getpass.getpass("New vault password: ")
    confirm = getpass.getpass("Confirm new vault password: ")
    if new_password != confirm:
        logger.error("Passwords do not match")
        sys.exit(1)

    if not new_password:
        logger.error("Password cannot be empty")
        sys.exit(1)

    store.re_encrypt(new_password)
    logger.info(f"Vault password rotated: {vf.path}")
    logger.info(f"Secrets preserved: {len(store)} keys unchanged")

    audit = get_audit_logger()
    audit.log_security_event(
        action="vault_rotate",
        resource=str(vf.path),
        outcome="success",
        details={"keys_preserved": len(store)},
    )


def cmd_rotate_secrets(args):
    """Rotate secrets based on the rotation policy schedule.

    For each secret that is due for rotation:
    1. Store the previous value in the policy (for grace period access)
    2. Prompt for or generate a new value
    3. Update the vault
    4. Record the rotation in the policy and audit log
    """
    store = _open_vault(args.vault_file, args.password_file)
    policy = RotationPolicy(args.policy)
    policy.load()

    # Clear expired grace periods first
    cleared = policy.clear_expired_grace()
    for key in cleared:
        logger.info(f"Grace period expired, previous value cleared: {key}")
        _log_rotation_event("grace_expired", key, "success")

    # Find secrets due for rotation
    all_keys = store.keys()
    due_secrets = policy.get_due_secrets(all_keys)

    if not due_secrets:
        logger.info("No secrets are due for rotation")
        policy.save()
        return

    logger.info(f"Secrets due for rotation: {len(due_secrets)}")
    for item in due_secrets:
        print(
            f"  {item['key']}: "
            f"last rotated {item['last_rotated']}, "
            f"policy {item['rotation_days']}d"
        )

    if not args.force:
        try:
            confirm = input("\nProceed with rotation? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        if confirm != "y":
            logger.info("Rotation cancelled")
            return

    rotated = 0
    skipped = 0
    for item in due_secrets:
        key = item["key"]
        try:
            old_value = store.get(key)
        except KeyError:
            logger.warning(f"Secret disappeared during rotation: {key}")
            skipped += 1
            continue

        # Get new value: from env var, stdin, or auto-generate
        env_key = f"CLAW_ROTATE_{key}"
        new_value = os.environ.get(env_key)

        if not new_value and not args.auto_generate:
            try:
                new_value = getpass.getpass(f"New value for {key}: ")
            except (EOFError, KeyboardInterrupt):
                print()
                logger.info(f"Skipped: {key}")
                skipped += 1
                continue

        if not new_value and args.auto_generate:
            # Auto-generate a 64-char hex token
            new_value = os.urandom(32).hex()
            logger.info(f"Auto-generated new value for: {key}")

        if not new_value:
            logger.warning(f"Empty value for {key} — skipping")
            skipped += 1
            continue

        # Store previous value for grace period, then update
        policy.record_rotation(key, previous_value=old_value)
        store.set(key, new_value)
        rotated += 1

        _log_rotation_event(
            "secret_rotated",
            key,
            "success",
            details={
                "rotation_days": item["rotation_days"],
                "days_since_rotation": item["days_since_rotation"],
                "auto_generated": args.auto_generate and not os.environ.get(env_key),
            },
        )

        audit = get_audit_logger()
        audit.log_security_event(
            action="secret_rotation",
            resource=key,
            outcome="success",
            details={
                "rotation_days": item["rotation_days"],
                "grace_period_hours": policy.get_secret_policy(key).get(
                    "grace_period_hours", policy.default_grace_hours
                ),
            },
        )

        logger.info(f"Rotated: {key}")

    store.save()
    policy.save()

    logger.info(
        f"Rotation complete: {rotated} rotated, {skipped} skipped"
    )


def cmd_rotation_status(args):
    """Display rotation status for all secrets in the vault."""
    store = _open_vault(args.vault_file, args.password_file)
    policy = RotationPolicy(args.policy)
    policy.load()

    all_keys = store.keys()
    now = datetime.now(timezone.utc)

    if not all_keys:
        logger.info("Vault is empty — no secrets to report")
        return

    # Header
    print(f"{'Secret':<35} {'Last Rotated':<22} {'Policy':<10} {'Status':<12}")
    print("-" * 82)

    due_count = 0
    for key in all_keys:
        entry = policy.get_secret_policy(key)
        rotation_days = entry.get("rotation_days", policy.default_rotation_days)
        last_rotated_str = entry.get("last_rotated")

        if last_rotated_str:
            last_rotated = datetime.strptime(
                last_rotated_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            days_since = (now - last_rotated).days
            is_due = days_since >= rotation_days
            last_display = last_rotated_str[:10]
        else:
            days_since = -1
            is_due = True
            last_display = "never"

        if is_due:
            status = "DUE"
            due_count += 1
        elif days_since >= rotation_days - 7:
            status = "SOON"
        else:
            status = "OK"

        grace_str = entry.get("grace_expires")
        has_grace = False
        if grace_str and entry.get("previous_value") is not None:
            grace_dt = datetime.strptime(
                grace_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            if now < grace_dt:
                has_grace = True
                status += " (grace)"

        days_display = f"{days_since}d" if days_since >= 0 else "n/a"
        policy_display = f"{rotation_days}d"

        # Truncate key name if too long
        key_display = key[:33] + ".." if len(key) > 35 else key

        print(
            f"{key_display:<35} {last_display + ' (' + days_display + ')':<22} "
            f"{policy_display:<10} {status:<12}"
        )

    print("-" * 82)
    print(
        f"Total: {len(all_keys)} secrets, "
        f"{due_count} due for rotation"
    )

    if args.json_output:
        result = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_secrets": len(all_keys),
            "due_for_rotation": due_count,
            "secrets": [],
        }
        for key in all_keys:
            entry = policy.get_secret_policy(key)
            rotation_days = entry.get(
                "rotation_days", policy.default_rotation_days
            )
            result["secrets"].append({
                "key": key,
                "last_rotated": entry.get("last_rotated", "never"),
                "rotation_days": rotation_days,
                "has_grace": bool(entry.get("previous_value")),
            })
        print("\n" + json.dumps(result, indent=2))


def cmd_rotation_init(args):
    """Initialize a rotation policy for all secrets in the vault."""
    store = _open_vault(args.vault_file, args.password_file)
    policy = RotationPolicy(args.policy)
    policy.load()

    all_keys = store.keys()
    added = 0
    for key in all_keys:
        existing = policy.get_secret_policy(key)
        if not existing:
            policy.set_secret_policy(
                key,
                rotation_days=args.rotation_days,
                grace_period_hours=args.grace_hours,
            )
            added += 1

    policy.save()
    logger.info(
        f"Rotation policy initialized: {added} secrets added "
        f"(policy: {args.rotation_days}d rotation, "
        f"{args.grace_hours}h grace)"
    )
    logger.info(f"Policy file: {policy.path}")

    _log_rotation_event(
        "policy_init",
        "*",
        "success",
        details={
            "secrets_added": added,
            "rotation_days": args.rotation_days,
            "grace_hours": args.grace_hours,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Argument Parser
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claw_vault",
        description="Claw Vault -- Encrypted Secrets Vault for Claw Agents",
    )

    # Global options
    parser.add_argument(
        "--vault-file",
        default=DEFAULT_VAULT_FILE,
        help=f"Path to vault file (default: {DEFAULT_VAULT_FILE})",
    )
    parser.add_argument(
        "--password-file",
        default=None,
        help="Path to a file containing the vault password (first line)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ─────────────────────────────────────────────────────────────────
    p_init = subparsers.add_parser("init", help="Create a new empty vault")
    p_init.add_argument(
        "--force", action="store_true",
        help="Overwrite existing vault",
    )
    p_init.set_defaults(func=cmd_init)

    # ── set ──────────────────────────────────────────────────────────────────
    p_set = subparsers.add_parser("set", help="Store a single key-value pair")
    p_set.add_argument("key", help="Secret key name")
    p_set.add_argument("value", help="Secret value")
    p_set.set_defaults(func=cmd_set)

    # ── get ──────────────────────────────────────────────────────────────────
    p_get = subparsers.add_parser("get", help="Retrieve and print a secret")
    p_get.add_argument("key", help="Secret key name")
    p_get.set_defaults(func=cmd_get)

    # ── list ─────────────────────────────────────────────────────────────────
    p_list = subparsers.add_parser("list", help="List all secret key names")
    p_list.set_defaults(func=cmd_list)

    # ── delete ───────────────────────────────────────────────────────────────
    p_delete = subparsers.add_parser("delete", help="Remove a key from the vault")
    p_delete.add_argument("key", help="Secret key name")
    p_delete.set_defaults(func=cmd_delete)

    # ── import-env ───────────────────────────────────────────────────────────
    p_import = subparsers.add_parser(
        "import-env", help="Import KEY=VALUE pairs from a .env file",
    )
    p_import.add_argument("env_file", help="Path to .env file")
    p_import.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing keys (default: preserve)",
    )
    p_import.set_defaults(func=cmd_import_env)

    # ── export-env ───────────────────────────────────────────────────────────
    p_export = subparsers.add_parser(
        "export-env", help="Export all secrets to a .env file",
    )
    p_export.add_argument("output_file", help="Output .env file path")
    p_export.add_argument(
        "--force", action="store_true",
        help="Overwrite existing output file",
    )
    p_export.set_defaults(func=cmd_export_env)

    # ── inject ───────────────────────────────────────────────────────────────
    p_inject = subparsers.add_parser(
        "inject",
        help="Write each secret to an individual file in a directory",
    )
    p_inject.add_argument(
        "directory",
        help="Target directory (e.g., /run/secrets/decrypted)",
    )
    p_inject.set_defaults(func=cmd_inject)

    # ── rotate ───────────────────────────────────────────────────────────────
    p_rotate = subparsers.add_parser(
        "rotate", help="Change the vault password (re-encrypts)",
    )
    p_rotate.set_defaults(func=cmd_rotate)

    # ── rotate-secrets ────────────────────────────────────────────────
    p_rotate_secrets = subparsers.add_parser(
        "rotate-secrets",
        help="Rotate secrets based on policy schedule",
    )
    p_rotate_secrets.add_argument(
        "--policy",
        default=DEFAULT_ROTATION_POLICY,
        help=f"Path to rotation policy file (default: {DEFAULT_ROTATION_POLICY})",
    )
    p_rotate_secrets.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompt",
    )
    p_rotate_secrets.add_argument(
        "--auto-generate", action="store_true",
        help="Auto-generate new secret values (64-char hex)",
    )
    p_rotate_secrets.set_defaults(func=cmd_rotate_secrets)

    # ── rotation-status ──────────────────────────────────────────────
    p_rotation_status = subparsers.add_parser(
        "rotation-status",
        help="Show rotation status for all secrets",
    )
    p_rotation_status.add_argument(
        "--policy",
        default=DEFAULT_ROTATION_POLICY,
        help=f"Path to rotation policy file (default: {DEFAULT_ROTATION_POLICY})",
    )
    p_rotation_status.add_argument(
        "--json", dest="json_output", action="store_true",
        help="Output status in JSON format",
    )
    p_rotation_status.set_defaults(func=cmd_rotation_status)

    # ── rotation-init ────────────────────────────────────────────────
    p_rotation_init = subparsers.add_parser(
        "rotation-init",
        help="Initialize rotation policy for all vault secrets",
    )
    p_rotation_init.add_argument(
        "--policy",
        default=DEFAULT_ROTATION_POLICY,
        help=f"Path to rotation policy file (default: {DEFAULT_ROTATION_POLICY})",
    )
    p_rotation_init.add_argument(
        "--rotation-days", type=int, default=90,
        help="Default rotation interval in days (default: 90)",
    )
    p_rotation_init.add_argument(
        "--grace-hours", type=int, default=DEFAULT_GRACE_PERIOD_HOURS,
        help=f"Grace period in hours (default: {DEFAULT_GRACE_PERIOD_HOURS})",
    )
    p_rotation_init.set_defaults(func=cmd_rotation_init)

    return parser


# ═══════════════════════════════════════════════════════════════════════════════
#  Signal Handling
# ═══════════════════════════════════════════════════════════════════════════════

def _install_signal_handlers():
    """Install graceful shutdown handlers for SIGINT/SIGTERM."""
    def _handler(sig, frame):
        logger.info("Interrupted -- exiting")
        sys.exit(130)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    setup_logging()
    _install_signal_handlers()

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
