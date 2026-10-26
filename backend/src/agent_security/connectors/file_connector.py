"""Safe File Connector with path traversal defense, chroot boundary, and blocklist."""

import os
from pathlib import Path
from typing import List, Optional

from agent_security.connectors.classification import DataClassification, OutboundInspectionEngine


class FileSecurityError(ValueError):
    """Raised when file operations violate path boundary or access forbidden files."""
    pass


FORBIDDEN_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".git",
    ".ssh",
    ".aws",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "credentials.json",
    "service_account.json",
    "passwd",
    "shadow",
    "sudoers",
}

FORBIDDEN_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".kdbx",
}


class SafeFileConnector:
    """Confines file system operations to a specified workspace root, blocking traversal escapes."""

    DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self, workspace_root: str | Path, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES):
        self.workspace_root = Path(workspace_root).resolve()
        self.max_file_bytes = max_file_bytes
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def resolve_safe_path(self, user_path: str) -> Path:
        """Resolve path and verify that it strictly remains within workspace boundary."""
        if not user_path or not user_path.strip():
            raise FileSecurityError("File path cannot be empty.")

        clean_path = user_path.strip()

        # Reject null bytes
        if "\0" in clean_path:
            raise FileSecurityError("Null bytes in file path are forbidden.")

        # Construct candidate path
        # If absolute path was given, ensure it stays within workspace root
        if os.path.isabs(clean_path):
            candidate = Path(clean_path).resolve()
        else:
            candidate = (self.workspace_root / clean_path).resolve()

        # Path traversal boundary check
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError:
            raise FileSecurityError(f"Access denied: Path '{user_path}' escapes workspace root.")

        # Blocklist check on file name and extensions
        filename = candidate.name.lower()
        if filename in FORBIDDEN_FILE_NAMES:
            raise FileSecurityError(f"Access denied: Forbidden file name '{candidate.name}'.")

        suffix = candidate.suffix.lower()
        if suffix in FORBIDDEN_EXTENSIONS:
            raise FileSecurityError(f"Access denied: Forbidden sensitive file extension '{suffix}'.")

        # Block any path components starting with hidden dots that match blocklist
        for part in candidate.parts:
            if part.lower() in FORBIDDEN_FILE_NAMES:
                raise FileSecurityError(f"Access denied: Path component '{part}' is forbidden.")

        return candidate

    def read_file(self, user_path: str) -> str:
        """Read file within workspace boundary, enforcing size limit."""
        target = self.resolve_safe_path(user_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {user_path}")
        if not target.is_file():
            raise FileSecurityError(f"Path is not a file: {user_path}")

        file_size = target.stat().st_size
        if file_size > self.max_file_bytes:
            raise FileSecurityError(
                f"File size {file_size} bytes exceeds maximum allowed {self.max_file_bytes} bytes."
            )

        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, user_path: str, content: str) -> int:
        """Write content within workspace boundary after outbound classification check."""
        target = self.resolve_safe_path(user_path)

        encoded = content.encode("utf-8")
        if len(encoded) > self.max_file_bytes:
            raise FileSecurityError(
                f"Content size {len(encoded)} bytes exceeds maximum allowed {self.max_file_bytes} bytes."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return len(encoded)

    def list_files(self, relative_subpath: str = "") -> List[str]:
        """List relative file paths within workspace directory."""
        dir_path = self.resolve_safe_path(relative_subpath or ".")
        if not dir_path.is_dir():
            raise FileSecurityError(f"Path is not a directory: {relative_subpath}")

        results: List[str] = []
        for p in dir_path.rglob("*"):
            if p.is_file():
                filename = p.name.lower()
                if filename not in FORBIDDEN_FILE_NAMES and p.suffix.lower() not in FORBIDDEN_EXTENSIONS:
                    try:
                        results.append(str(p.relative_to(self.workspace_root).as_posix()))
                    except ValueError:
                        pass
        return sorted(results)
