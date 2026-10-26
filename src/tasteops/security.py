"""TasteOps Core Security Utilities.

Provides defense-in-depth security functions for:
- SSRF prevention (validates external connector URLs against private/metadata IPs with fail-closed DNS resolution)
- Constant-time secret comparison (mitigates timing attacks)
- Identifier and path sanitization (mitigates path traversal)

Outbound Connection-Time Address Policy & DNS Rebinding Defenses:
- Outbound connector transports must enforce pre-resolution validation via `validate_safe_url`.
- To prevent DNS rebinding (TOCTOU between resolution and connection), connectors must
  not cache resolved IPs across sessions or trust short-TTL external DNS responses.
- HTTP transports should pin the validated IP or re-verify the resolved socket address
  at socket connect time against `BLOCKED_IP_NETWORKS`.
- Unrestricted HTTP redirects to arbitrary external endpoints are strictly prohibited.
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
    ipaddress.ip_network("0.0.0.0/8"),  # Current network / Unspecified IPv4
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
    ipaddress.ip_network("224.0.0.0/4"),  # IPv4 Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::/128"),  # IPv6 Unspecified
    ipaddress.ip_network("::1/128"),  # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
    ipaddress.ip_network("ff00::/8"),  # IPv6 Multicast
]


def validate_safe_url(
    url: str,
    allow_private: bool = False,
    allowed_hosts: list[str] | set[str] | None = None,
) -> bool:
    """Validates that a URL is well-formed and does not target private or metadata IPs (SSRF).

    Args:
        url: The candidate URL string to evaluate.
        allow_private: If True, allows private network IPs (for internal testing only).
        allowed_hosts: Optional explicit host/domain allowlist.

    Returns:
        True if the URL is safe for external dispatch.

    Raises:
        ValueError: If the URL scheme is unsupported, targets a restricted IP, or violates host allowlist.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    parsed = urlparse(url.strip())

    # 1. Scheme Validation: strictly HTTP or HTTPS
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
        )

    # Disallow credentials in URLs to prevent userinfo spoofing
    if parsed.username or parsed.password:
        raise ValueError(
            "URL credentials (userinfo) are prohibited in external dispatch endpoints."
        )

    # 2. Hostname Validation
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL does not contain a valid hostname.")

    lower_host = hostname.lower()

    # Reject cloud metadata special hostnames directly
    if lower_host in (
        "metadata.google.internal",
        "instance-data",
        "169.254.169.254",
        "metadata.platform",
    ):
        raise ValueError(
            f"SSRF Protection: Access to cloud metadata endpoint '{hostname}' is blocked."
        )

    # Enforce strict host allowlist if configured
    if allowed_hosts:
        normalized_allowed = {h.lower().strip() for h in allowed_hosts if h.strip()}
        matched = False
        for allowed in normalized_allowed:
            if allowed.startswith("*."):
                domain_suffix = allowed[2:]
                if lower_host == domain_suffix or lower_host.endswith(
                    "." + domain_suffix
                ):
                    matched = True
                    break
            elif lower_host == allowed:
                matched = True
                break
        if not matched:
            raise ValueError(
                f"SSRF Protection: Hostname '{hostname}' is not in the allowed hosts list: {sorted(normalized_allowed)}."
            )

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

            # Cloud metadata, link-local, and unspecified subnets are blocked UNCONDITIONALLY
            if (
                target_ip in ipaddress.ip_network("169.254.0.0/16")
                or target_ip in ipaddress.ip_network("fe80::/10")
                or target_ip in ipaddress.ip_network("0.0.0.0/8")
                or target_ip in ipaddress.ip_network("::/128")
            ):
                raise ValueError(
                    f"SSRF Protection: Access to cloud metadata / link-local endpoint '{hostname}' is blocked."
                )

            if not allow_private:
                for blocked_net in BLOCKED_IP_NETWORKS:
                    if target_ip in blocked_net:
                        raise ValueError(
                            f"SSRF Protection: Hostname '{hostname}' resolves to restricted IP address {resolved_ip}."
                        )
    except (socket.gaierror, socket.herror) as exc:
        logger.error(
            "DNS resolution failed during SSRF check for '%s': %s", hostname, exc
        )
        if not allow_private:
            # Strict Fail-Closed: Outbound dispatch fails closed on DNS resolution failures
            raise ValueError(
                f"SSRF Protection: DNS resolution failed for '{hostname}': {exc}"
            ) from exc

    return True


def validate_safe_redirect(
    redirect_target: str,
    original_url: str,
    allow_private: bool = False,
    allowed_hosts: list[str] | set[str] | None = None,
) -> str:
    """Validates HTTP redirect destinations against SSRF policy and returns resolved target URL."""
    from urllib.parse import urljoin

    resolved_target = urljoin(original_url, redirect_target)
    validate_safe_url(
        resolved_target, allow_private=allow_private, allowed_hosts=allowed_hosts
    )
    return resolved_target


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
