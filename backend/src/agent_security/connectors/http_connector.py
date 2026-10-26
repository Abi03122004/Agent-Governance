"""SSRF-Safe HTTP Connector with strict DNS/IP validation, metadata blocking, and size limits."""

import ipaddress
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import httpx

from agent_security.connectors.classification import DataClassification, OutboundInspectionEngine


class SSRFSecurityError(ValueError):
    """Raised when an outbound HTTP request targets a blocked IP, loopback, or cloud metadata."""
    pass


FORBIDDEN_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.aws",
    "instance-data",
}

# Special cloud metadata & link-local IP blocks
METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),  # Alibaba cloud metadata
}


def is_prohibited_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to loopback, private, link-local, or cloud metadata ranges."""
    if ip_obj in METADATA_IPS:
        return True
    if ip_obj.is_loopback:
        return True
    if ip_obj.is_private:
        return True
    if ip_obj.is_link_local:
        return True
    if ip_obj.is_multicast:
        return True
    if ip_obj.is_reserved:
        return True
    if ip_obj.is_unspecified:
        return True

    # Check Carrier-Grade NAT (100.64.0.0/10)
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    if ip_obj in cgnat:
        return True

    return False


def validate_url(url: str) -> Tuple[str, List[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    """Validate URL scheme and resolve DNS to ensure all target IPs are public and safe.
    Returns (hostname, resolved_safe_ips).
    Raises SSRFSecurityError if unsafe.
    """
    if not url:
        raise SSRFSecurityError("URL cannot be empty")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise SSRFSecurityError(f"Prohibited URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed.")

    if parsed.username or parsed.password:
        raise SSRFSecurityError("Userinfo in URL is forbidden.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL is missing hostname.")

    hostname_clean = hostname.strip().lower()
    if hostname_clean in FORBIDDEN_HOSTNAMES:
        raise SSRFSecurityError(f"Access to prohibited hostname '{hostname}' is blocked.")

    # Check if host is direct IP
    try:
        ip_direct = ipaddress.ip_address(hostname_clean)
    except ValueError:
        ip_direct = None

    if ip_direct is not None:
        if is_prohibited_ip(ip_direct):
            raise SSRFSecurityError(f"Direct connection to private/loopback/metadata IP '{ip_direct}' is blocked.")
        return hostname_clean, [ip_direct]

    # Resolve domain via DNS
    try:
        addr_infos = socket.getaddrinfo(hostname_clean, None)
    except socket.gaierror as e:
        raise SSRFSecurityError(f"DNS resolution failed for hostname '{hostname}': {e}")

    resolved_ips: List[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in addr_infos:
        ip_str = info[4][0]
        ip_obj = ipaddress.ip_address(ip_str)
        if is_prohibited_ip(ip_obj):
            raise SSRFSecurityError(
                f"Target hostname '{hostname}' resolved to prohibited IP '{ip_str}' (private, loopback, or metadata)."
            )
        resolved_ips.append(ip_obj)

    if not resolved_ips:
        raise SSRFSecurityError(f"No IP addresses resolved for hostname '{hostname}'")

    return hostname_clean, resolved_ips


class SSRFSafeHttpClient:
    """Hardened HTTP client with DNS validation, redirect revalidation, and response size limits."""

    DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(
        self,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_allowed_classification: DataClassification = DataClassification.INTERNAL,
    ):
        self.max_response_bytes = max_response_bytes
        self.timeout = timeout
        self.max_allowed_classification = max_allowed_classification

    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        follow_redirects: bool = False,
    ) -> Dict[str, Any]:
        """Perform SSRF-safe HTTP request with pre-flight DNS check and outbound payload inspection."""
        # 1. SSRF URL and DNS pre-flight check
        validate_url(url)

        # 2. Outbound payload inspection
        if json_data is not None:
            permitted, violations, _ = OutboundInspectionEngine.inspect_payload(
                json_data, self.max_allowed_classification
            )
            if not permitted:
                raise SSRFSecurityError(
                    f"Outbound payload blocked by inspection engine: {'; '.join(violations)}"
                )

        # 3. Execute request safely
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            current_url = url
            redirect_count = 0
            max_redirects = 5

            while True:
                req = client.build_request(method, current_url, headers=headers, json=json_data)
                response = await client.send(req, stream=True)

                if response.is_redirect and follow_redirects:
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        raise SSRFSecurityError("Exceeded maximum redirects (5)")
                    redirect_url = response.headers.get("Location")
                    if not redirect_url:
                        break
                    # Re-validate redirect target to prevent DNS rebinding / redirect bypass
                    validate_url(redirect_url)
                    current_url = redirect_url
                    continue

                # Stream response with size cap
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_response_bytes:
                        raise SSRFSecurityError(
                            f"Response size exceeded limit of {self.max_response_bytes} bytes"
                        )

                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": content.decode("utf-8", errors="replace"),
                    "final_url": current_url,
                }
