"""Safe Database Connector with SQL injection defense, parameterized query enforcement, and result redaction."""

import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.core.redaction import redact_sensitive_payload


class DBSecurityError(ValueError):
    """Raised when a database query violates security policy or contains SQL injection."""
    pass


FORBIDDEN_SQL_KEYWORDS = [
    re.compile(r"\bDROP\s+(TABLE|DATABASE|VIEW|INDEX|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bGRANT\b", re.IGNORECASE),
    re.compile(r"\bREVOKE\b", re.IGNORECASE),
    re.compile(r"\bATTACH\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\bEXEC(\s+|UTABLE)", re.IGNORECASE),
]

SQLI_PATTERN_CHECKS = [
    re.compile(r"(--|/\*|\*/)", re.IGNORECASE),  # SQL comments
    re.compile(r";\s*\S+", re.IGNORECASE),  # Stacked/multi-statements
    re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE),  # UNION injections
    re.compile(r"('\s+OR\s+'1'='1|1=1)", re.IGNORECASE),  # Tautologies
]


def validate_sql_statement(sql_query: str, read_only: bool = True) -> str:
    """Validates that a SQL query is well-formed, single-statement, and free of injection patterns."""
    if not sql_query or not sql_query.strip():
        raise DBSecurityError("SQL query cannot be empty.")

    cleaned = sql_query.strip()

    # Check for forbidden DDL / admin keywords
    for pattern in FORBIDDEN_SQL_KEYWORDS:
        if pattern.search(cleaned):
            raise DBSecurityError(f"Destructive SQL command forbidden by security policy: {pattern.pattern}")

    # Check for stacked multi-statements and SQL injection patterns
    for pattern in SQLI_PATTERN_CHECKS:
        if pattern.search(cleaned):
            raise DBSecurityError(f"Suspicious SQL injection or multi-statement pattern detected: {pattern.pattern}")

    # Enforce read-only if required
    if read_only:
        first_word = cleaned.split()[0].upper()
        if first_word not in {"SELECT", "WITH", "EXPLAIN"}:
            raise DBSecurityError(f"Operation '{first_word}' is forbidden in read-only database mode.")

    return cleaned


class SafeDatabaseConnector:
    """Executes validated, strictly parameterized queries with automated sensitive data redaction."""

    def __init__(self, db: AsyncSession, read_only: bool = True):
        self.db = db
        self.read_only = read_only

    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        redact_results: bool = True,
    ) -> List[Dict[str, Any]]:
        """Executes a strictly parameterized query, validating SQL and scrubbing output."""
        validated_sql = validate_sql_statement(query, read_only=self.read_only)
        bind_params = params or {}

        # Parameter type checking: parameters must be a dictionary or primitive values
        if not isinstance(bind_params, dict):
            raise DBSecurityError("Query parameters must be provided as a dictionary for safe binding.")

        stmt = text(validated_sql)
        result = await self.db.execute(stmt, bind_params)

        if not result.returns_rows:
            return []

        rows = result.mappings().all()
        raw_data = [dict(r) for r in rows]

        if redact_results:
            return redact_sensitive_payload(raw_data)
        return raw_data
