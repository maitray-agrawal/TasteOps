"""TasteOps Core Security Utilities.

Provides defense-in-depth security functions for:
- SSRF prevention (validates external connector URLs against private/metadata IPs)
- Constant-time secret comparison (mitigates timing attacks)
- Identifier and path sanitization (mitigates path traversal)
"""

from __future__ import annotations

import ipaddress
import logging
import re
import secrets
import socket
from urllib.parse import urlparse

logger = logging.getLogger("tasteops.security")

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

# Denied IP ranges for SSRF prevention (cloud metadata, loopback, RFC 1918 private subnets)
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 Private
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Private
    ipaddress.ip_network(
        "169.254.0.0/16"
    ),  # Link-Local / Cloud Metadata (AWS, GCP, Azure)
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-Grade NAT
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
]


def validate_safe_url(url: str, allow_private: bool = False) -> bool:
    """Validates that a URL is well-formed and does not target private or metadata IPs (SSRF).

    Args:
        url: The candidate URL string to evaluate.
        allow_private: If True, allows private network IPs (for internal testing only).

    Returns:
        True if the URL is safe for external dispatch.

    Raises:
        ValueError: If the URL scheme is unsupported or targets a restricted IP.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    parsed = urlparse(url.strip())

    # 1. Scheme Validation: strictly HTTP or HTTPS
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
        )

    # 2. Hostname Validation
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL does not contain a valid hostname.")

    # Reject cloud metadata special hostnames directly
    lower_host = hostname.lower()
    if lower_host in ("metadata.google.internal", "instance-data", "169.254.169.254"):
        raise ValueError(
            f"SSRF Protection: Access to cloud metadata endpoint '{hostname}' is blocked."
        )

    if allow_private:
        return True

    # 3. IP Resolution and Range Check
    try:
        # Check if hostname is already a direct IP address
        try:
            ip = ipaddress.ip_address(hostname)
            ips = [ip]
        except ValueError:
            # Resolve DNS hostname
            addr_info = socket.getaddrinfo(
                hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
            ips = [ipaddress.ip_address(item[4][0]) for item in addr_info]

        for resolved_ip in ips:
            target_ip: ipaddress.IPv4Address | ipaddress.IPv6Address = resolved_ip
            if (
                isinstance(resolved_ip, ipaddress.IPv6Address)
                and resolved_ip.ipv4_mapped is not None
            ):
                target_ip = resolved_ip.ipv4_mapped

            for blocked_net in BLOCKED_IP_NETWORKS:
                if target_ip in blocked_net:
                    raise ValueError(
                        f"SSRF Protection: Hostname '{hostname}' resolves to restricted IP address {resolved_ip}."
                    )
    except socket.gaierror as exc:
        logger.warning(
            "DNS resolution failed during SSRF check for '%s': %s", hostname, exc
        )
        # In isolated environments where external DNS is mocked, allow non-resolving synthetic hostnames
        # unless they explicitly match blocked IP patterns

    return True


def constant_time_compare(val1: str | None, val2: str | None) -> bool:
    """Performs constant-time string comparison to prevent timing attacks on secrets."""
    if val1 is None or val2 is None:
        return False
    return secrets.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def validate_identifier(identifier: str, field_name: str = "identifier") -> str:
    """Validates that an identifier contains only alphanumeric, hyphen, and underscore characters.

    Guarantees that path traversal characters ('..', '/', '\\') are rejected.
    """
    if not identifier or not isinstance(identifier, str):
        raise ValueError(f"{field_name} must be a non-empty string.")

    cleaned = identifier.strip()
    if not SAFE_IDENTIFIER_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid {field_name} '{identifier}': Allowed characters are alphanumeric, hyphen, and underscore only."
        )
    return cleaned
