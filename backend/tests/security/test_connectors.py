"""Tests for Phase 5: Hardened Connectors & Data Classification Engine.

Verifies:
1. SSRF-safe HTTP client with DNS resolution validation, link-local/cloud metadata blocking, redirect re-validation, and response size caps.
2. Safe File connector with strict chroot confinement, path traversal defenses, sensitive file blocklists, and size caps.
3. Safe Database connector with SQL injection defenses, DDL blocking, tautology detection, parameterized execution, and output redaction.
4. Outbound data classification and inspection engine (PII, financial, credential detection, classification hierarchies).
"""

import ipaddress
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_security.connectors.classification import (
    ClassificationTag,
    DataClassification,
    OutboundInspectionEngine,
    ProvenanceRecord,
)
from agent_security.connectors.http_connector import (
    FORBIDDEN_HOSTNAMES,
    METADATA_IPS,
    SSRFSafeHttpClient,
    SSRFSecurityError,
    is_prohibited_ip,
    validate_url,
)
from agent_security.connectors.file_connector import (
    FORBIDDEN_EXTENSIONS,
    FORBIDDEN_FILE_NAMES,
    FileSecurityError,
    SafeFileConnector,
)
from agent_security.connectors.db_connector import (
    DBSecurityError,
    SafeDatabaseConnector,
    validate_sql_statement,
)


# =====================================================================
# 1. SSRF & HTTP Connector Security Tests
# =====================================================================

def test_is_prohibited_ip_matrix():
    """Verify classification of loopback, private, link-local, CGNAT, and cloud metadata IPs."""
    # Loopback
    assert is_prohibited_ip(ipaddress.ip_address("127.0.0.1")) is True
    assert is_prohibited_ip(ipaddress.ip_address("127.0.0.2")) is True
    assert is_prohibited_ip(ipaddress.ip_address("::1")) is True

    # RFC 1918 Private
    assert is_prohibited_ip(ipaddress.ip_address("10.0.0.1")) is True
    assert is_prohibited_ip(ipaddress.ip_address("172.16.0.1")) is True
    assert is_prohibited_ip(ipaddress.ip_address("192.168.1.1")) is True

    # Cloud Metadata & Link-local
    assert is_prohibited_ip(ipaddress.ip_address("169.254.169.254")) is True
    assert is_prohibited_ip(ipaddress.ip_address("169.254.1.1")) is True
    assert is_prohibited_ip(ipaddress.ip_address("100.100.100.200")) is True  # Alibaba metadata

    # CGNAT
    assert is_prohibited_ip(ipaddress.ip_address("100.64.0.1")) is True

    # Public IP
    assert is_prohibited_ip(ipaddress.ip_address("8.8.8.8")) is False
    assert is_prohibited_ip(ipaddress.ip_address("93.184.216.34")) is False


def test_validate_url_ssrf_blocking():
    """Verify validate_url blocks forbidden schemes, userinfo, metadata hosts, and private IPs."""
    # Forbidden schemes
    for bad_scheme in ["file:///etc/passwd", "ftp://ftp.example.com", "gopher://127.0.0.1:6379", "javascript:alert(1)"]:
        with pytest.raises(SSRFSecurityError, match="Prohibited URL scheme"):
            validate_url(bad_scheme)

    # Empty URL
    with pytest.raises(SSRFSecurityError, match="URL cannot be empty"):
        validate_url("")

    # Userinfo in URL
    with pytest.raises(SSRFSecurityError, match="Userinfo in URL is forbidden"):
        validate_url("http://admin:secret@example.com/api")

    # Forbidden hostnames
    for bad_host in FORBIDDEN_HOSTNAMES:
        with pytest.raises(SSRFSecurityError, match="prohibited hostname"):
            validate_url(f"http://{bad_host}/path")

    # Direct private / metadata IPs in URL
    for blocked_ip in ["127.0.0.1", "10.1.2.3", "192.168.0.1", "172.16.1.1", "169.254.169.254"]:
        with pytest.raises(SSRFSecurityError, match="Direct connection to private/loopback/metadata IP"):
            validate_url(f"http://{blocked_ip}/metrics")


def test_validate_url_dns_resolution_private_ip():
    """Verify DNS rebinding / domain resolving to internal IP is caught during resolution."""
    # Simulate a domain that resolves to 127.0.0.1 or 169.254.169.254
    fake_dns_result = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))
    ]
    with patch("socket.getaddrinfo", return_value=fake_dns_result):
        with pytest.raises(SSRFSecurityError, match="resolved to prohibited IP"):
            validate_url("http://evil-attacker-domain.internal/secret")


def test_validate_url_public_domain_success():
    """Verify public domain name resolves to allowed public IP."""
    fake_public_dns = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ]
    with patch("socket.getaddrinfo", return_value=fake_public_dns):
        host, ips = validate_url("https://example.com/api/v1/data")
        assert host == "example.com"
        assert len(ips) == 1
        assert str(ips[0]) == "93.184.216.34"


@pytest.mark.asyncio
async def test_ssrf_client_blocks_classified_outbound_payload():
    """Verify SSRFSafeHttpClient scans outbound payloads before transmitting."""
    client = SSRFSafeHttpClient(max_allowed_classification=DataClassification.INTERNAL)

    # Payload with restricted API token should be blocked before network call
    payload_with_secret = {
        "action": "sync",
        "api_key": "mock_live_secret_key_1234567890abcdef",
    }
    fake_public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=fake_public_dns):
        with pytest.raises(SSRFSecurityError, match="Outbound payload blocked by inspection engine"):
            await client.request("POST", "https://api.external.com/sync", json_data=payload_with_secret)


@pytest.mark.asyncio
async def test_ssrf_client_redirect_revalidation():
    """Verify SSRFSafeHttpClient validates redirect targets, preventing redirect to metadata."""
    client = SSRFSafeHttpClient()

    mock_resp1 = MagicMock()
    mock_resp1.is_redirect = True
    mock_resp1.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    fake_public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=fake_public_dns):
        with patch("httpx.AsyncClient.send", return_value=mock_resp1):
            with pytest.raises(SSRFSecurityError, match="Direct connection to private/loopback/metadata IP"):
                await client.request("GET", "https://api.example.com/redirect", follow_redirects=True)


# =====================================================================
# 2. Safe File Connector Security Tests
# =====================================================================

def test_file_connector_chroot_confinement_and_traversal(tmp_path: Path):
    """Verify SafeFileConnector strictly enforces workspace confinement and blocks directory traversal."""
    workspace = tmp_path / "agent_workspace"
    connector = SafeFileConnector(workspace_root=workspace)

    # Normal write and read within workspace
    bytes_written = connector.write_file("data/report.txt", "Quarterly audit results")
    assert bytes_written > 0
    content = connector.read_file("data/report.txt")
    assert content == "Quarterly audit results"

    # Directory traversal escapes
    traversal_paths = [
        "../outside.txt",
        "data/../../outside.txt",
        "../../etc/passwd",
        "/etc/shadow",
    ]
    for bad_path in traversal_paths:
        with pytest.raises(FileSecurityError, match="escapes workspace root"):
            connector.resolve_safe_path(bad_path)

    # Null byte attack
    with pytest.raises(FileSecurityError, match="Null bytes in file path are forbidden"):
        connector.resolve_safe_path("data/safe.txt\0.evil")

    # Empty path
    with pytest.raises(FileSecurityError, match="File path cannot be empty"):
        connector.resolve_safe_path("")


def test_file_connector_blocks_forbidden_names_and_extensions(tmp_path: Path):
    """Verify SafeFileConnector blocks sensitive system files and credentials."""
    connector = SafeFileConnector(workspace_root=tmp_path)

    for forbidden_file in FORBIDDEN_FILE_NAMES:
        with pytest.raises(FileSecurityError, match="Forbidden file name|Path component"):
            connector.resolve_safe_path(forbidden_file)

    for forbidden_ext in FORBIDDEN_EXTENSIONS:
        with pytest.raises(FileSecurityError, match="Forbidden sensitive file extension"):
            connector.resolve_safe_path(f"certs/server{forbidden_ext}")


def test_file_connector_size_limit(tmp_path: Path):
    """Verify SafeFileConnector rejects oversized file writes."""
    connector = SafeFileConnector(workspace_root=tmp_path, max_file_bytes=100)

    oversized_content = "A" * 150
    with pytest.raises(FileSecurityError, match="exceeds maximum allowed 100 bytes"):
        connector.write_file("big.txt", oversized_content)


def test_file_connector_list_files(tmp_path: Path):
    """Verify SafeFileConnector list_files filters out forbidden files."""
    connector = SafeFileConnector(workspace_root=tmp_path)
    connector.write_file("public/doc1.txt", "hello")
    connector.write_file("public/doc2.txt", "world")

    files = connector.list_files()
    assert "public/doc1.txt" in files
    assert "public/doc2.txt" in files


# =====================================================================
# 3. Safe Database Connector Security Tests
# =====================================================================

def test_validate_sql_statement_destructive_ddl_and_admin():
    """Verify validate_sql_statement blocks DDL, TRUNCATE, and administrative commands."""
    forbidden_queries = [
        "DROP TABLE users;",
        "DROP DATABASE production;",
        "TRUNCATE TABLE audit_logs;",
        "ALTER TABLE agents ADD COLUMN backdoor text;",
        "GRANT ALL PRIVILEGES ON *.* TO 'hacker'@'%';",
        "REVOKE SELECT ON users FROM 'analyst';",
        "ATTACH DATABASE '/tmp/injected.db' AS injected;",
        "EXEC xp_cmdshell('whoami');",
    ]
    for query in forbidden_queries:
        with pytest.raises(DBSecurityError, match="Destructive SQL command forbidden"):
            validate_sql_statement(query, read_only=False)


def test_validate_sql_statement_sqli_patterns():
    """Verify validate_sql_statement catches multi-statement, comments, and tautology injections."""
    sqli_queries = [
        "SELECT * FROM agents; SELECT * FROM credentials;",
        "SELECT * FROM agents WHERE name = 'admin' -- comment injection",
        "SELECT * FROM agents WHERE name = 'admin' /* comment block */",
        "SELECT id FROM agents UNION SELECT password FROM users",
        "SELECT * FROM agents WHERE id = '1' OR '1'='1'",
        "SELECT * FROM agents WHERE 1=1",
    ]
    for query in sqli_queries:
        with pytest.raises(DBSecurityError, match="Suspicious SQL injection or multi-statement pattern"):
            validate_sql_statement(query, read_only=False)

    # Empty query
    with pytest.raises(DBSecurityError, match="SQL query cannot be empty"):
        validate_sql_statement("   ")


def test_validate_sql_statement_read_only_enforcement():
    """Verify read-only mode blocks INSERT, UPDATE, DELETE while allowing SELECT and WITH."""
    # Write attempts in read-only mode
    with pytest.raises(DBSecurityError, match="Operation 'INSERT' is forbidden in read-only database mode"):
        validate_sql_statement("INSERT INTO agents (id, name) VALUES ('1', 'bad')", read_only=True)

    with pytest.raises(DBSecurityError, match="Operation 'UPDATE' is forbidden in read-only database mode"):
        validate_sql_statement("UPDATE agents SET name = 'compromised'", read_only=True)

    # Valid read-only queries
    valid_select = "SELECT id, name FROM agents WHERE status = :status"
    assert validate_sql_statement(valid_select, read_only=True) == valid_select

    valid_with = "WITH active_agents AS (SELECT id FROM agents WHERE status = 'active') SELECT * FROM active_agents"
    assert validate_sql_statement(valid_with, read_only=True) == valid_with


@pytest.mark.asyncio
async def test_safe_database_connector_execution_and_redaction():
    """Verify SafeDatabaseConnector executes parameterized queries and redacts sensitive columns."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create test table
        from sqlalchemy import text
        await session.execute(text("CREATE TABLE test_secrets (id TEXT, agent_name TEXT, api_key TEXT)"))
        await session.execute(
            text("INSERT INTO test_secrets VALUES ('1', 'FinAgent', 'mock_vault_token_1234567890abcdef')")
        )
        await session.commit()

        connector = SafeDatabaseConnector(db=session, read_only=True)

        # 1. Parameterized query with dictionary binding
        results = await connector.execute_query(
            "SELECT id, agent_name, api_key FROM test_secrets WHERE id = :id",
            params={"id": "1"},
            redact_results=True,
        )
        assert len(results) == 1
        row = results[0]
        assert row["id"] == "1"
        assert row["agent_name"] == "FinAgent"
        # The sensitive column 'api_key' must be redacted!
        assert row["api_key"] == "[REDACTED_SECRET]"

        # 2. Reject non-dict parameters
        with pytest.raises(DBSecurityError, match="Query parameters must be provided as a dictionary"):
            await connector.execute_query(
                "SELECT id FROM test_secrets",
                params=["invalid", "list"],  # type: ignore
            )

    await engine.dispose()


# =====================================================================
# 4. Data Classification & Outbound Inspection Tests
# =====================================================================

def test_data_classification_text_scoring():
    """Verify classify_text accurately identifies secrets, PII, financial info, and internal text."""
    # System Secret / Credential
    cls_sec, tags_sec = OutboundInspectionEngine.classify_text("Authorization: Bearer mock_access_token_abcdef1234567890")
    assert cls_sec == DataClassification.RESTRICTED
    assert ClassificationTag.CREDENTIALS in tags_sec

    # Financial / Credit Card
    cls_fin, tags_fin = OutboundInspectionEngine.classify_text("Billing account: 4532-1234-5678-9012")
    assert cls_fin == DataClassification.CONFIDENTIAL
    assert ClassificationTag.FINANCIAL in tags_fin

    # PII / SSN
    cls_pii, tags_pii = OutboundInspectionEngine.classify_text("Social security reference: 123-45-6789")
    assert cls_pii == DataClassification.CONFIDENTIAL
    assert ClassificationTag.PII in tags_pii

    # Standard Internal Data
    cls_int, tags_int = OutboundInspectionEngine.classify_text("Quarterly roadmap review meeting minutes.")
    assert cls_int == DataClassification.INTERNAL
    assert len(tags_int) == 0


def test_inspect_payload_sensitive_key_redaction_and_hierarchy():
    """Verify inspect_payload blocks sensitive keys and enforces classification ceilings."""
    # 1. Payload with forbidden sensitive key
    payload_with_keys = {
        "status": "ok",
        "db_password": "supersecretpassword123",
        "nested": {"client_secret": "my-secret-key"},
    }
    permitted, violations, sanitized = OutboundInspectionEngine.inspect_payload(
        payload_with_keys, max_allowed_classification=DataClassification.RESTRICTED
    )
    assert permitted is False
    assert any("db_password" in v for v in violations)
    assert sanitized["db_password"] == "[REDACTED_SECRET]"
    assert sanitized["nested"]["client_secret"] == "[REDACTED_SECRET]"

    # 2. Payload with confidential data when max allowed is INTERNAL
    payload_pii = {
        "user_summary": "Customer SSN: 123-45-6789 registered yesterday.",
    }
    permitted, violations, _ = OutboundInspectionEngine.inspect_payload(
        payload_pii, max_allowed_classification=DataClassification.INTERNAL
    )
    assert permitted is False
    assert any("Data classification violation" in v for v in violations)

    # 3. Benign payload under allowed classification passes cleanly
    benign_payload = {
        "service": "agent-gateway",
        "healthy": True,
        "metrics": {"requests_per_sec": 42},
    }
    permitted, violations, sanitized = OutboundInspectionEngine.inspect_payload(
        benign_payload, max_allowed_classification=DataClassification.INTERNAL
    )
    assert permitted is True
    assert len(violations) == 0
    assert sanitized == benign_payload
