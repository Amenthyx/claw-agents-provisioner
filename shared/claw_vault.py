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

Requirements:
    Python 3.8+
    cryptography  (pip install cryptography)
"""

import argparse
import getpass
import json
import logging
import os
import signal
import sys
import tempfile
from pathlib import Path

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


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

VAULT_MAGIC = b"CLAWVAULT1"          # 10 bytes — file format identifier
SALT_LENGTH = 16                      # bytes
PBKDF2_ITERATIONS = 480_000
DEFAULT_VAULT_FILE = "secrets.vault"


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
        except Exception:
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


def cmd_set(args):
    """Store a single key-value pair."""
    store = _open_vault(args.vault_file, args.password_file)
    store.set(args.key, args.value)
    store.save()
    logger.info(f"Secret stored: {args.key}")


def cmd_get(args):
    """Retrieve and print a single secret."""
    store = _open_vault(args.vault_file, args.password_file)
    try:
        value = store.get(args.key)
        # Print raw value (no logging prefix) for piping
        print(value)
    except KeyError:
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
    except KeyError:
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
        except Exception:
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
