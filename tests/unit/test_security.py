"""Unit tests for TasteOps Core Security Utilities (SSRF, timing attacks, path traversal)."""

from __future__ import annotations

import pytest

from tasteops.security import (
    constant_time_compare,
    validate_identifier,
    validate_safe_url,
)


class TestValidateSafeUrl:
    """Tests for SSRF prevention and outbound URL validation."""

    def test_valid_public_https_url(self):
        assert validate_safe_url("https://api.spotify.com/v1/search") is True
        assert validate_safe_url("https://api.sendgrid.com/v3/mail/send") is True
        assert validate_safe_url("http://example.com/webhook") is True

    def test_empty_or_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_safe_url("")
        with pytest.raises(ValueError, match="non-empty string"):
            validate_safe_url(None)  # type: ignore[arg-type]

    def test_disallowed_schemes_raise_value_error(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_safe_url("file:///etc/passwd")
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_safe_url("ftp://ftp.example.com")
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_safe_url("gopher://gopher.floodgap.com")

    def test_missing_hostname_raises_value_error(self):
        with pytest.raises(ValueError, match="valid hostname"):
            validate_safe_url("https://")

    def test_cloud_metadata_endpoints_blocked(self):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://169.254.169.254/latest/meta-data/")
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://metadata.google.internal/computeMetadata/v1/")
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://instance-data/latest/")

    def test_loopback_addresses_blocked(self):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://127.0.0.1:8000/internal")
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://127.0.0.2:9000/")

    def test_rfc1918_private_addresses_blocked(self):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://10.0.0.5/api")
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://172.16.0.1/admin")
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_safe_url("http://192.168.1.1/setup")

    def test_allow_private_flag_permits_private_ips(self):
        assert validate_safe_url("http://10.0.0.5/api", allow_private=True) is True
        assert validate_safe_url("http://192.168.1.1/setup", allow_private=True) is True


class TestConstantTimeCompare:
    """Tests for constant-time string comparison to prevent timing attacks."""

    def test_identical_strings_return_true(self):
        assert constant_time_compare("super_secret_token", "super_secret_token") is True
        assert constant_time_compare("", "") is True

    def test_different_strings_return_false(self):
        assert constant_time_compare("secret_a", "secret_b") is False
        assert constant_time_compare("abc", "abcdef") is False

    def test_none_values_return_false(self):
        assert constant_time_compare(None, "token") is False
        assert constant_time_compare("token", None) is False
        assert constant_time_compare(None, None) is False


class TestValidateIdentifier:
    """Tests for identifier sanitization and path traversal prevention."""

    def test_valid_alphanumeric_identifiers(self):
        assert validate_identifier("session_123") == "session_123"
        assert validate_identifier("space-venue-shibuya") == "space-venue-shibuya"
        assert validate_identifier("  plan_v2  ") == "plan_v2"

    def test_path_traversal_characters_rejected(self):
        with pytest.raises(ValueError, match="Allowed characters"):
            validate_identifier("../etc/passwd")
        with pytest.raises(ValueError, match="Allowed characters"):
            validate_identifier("..\\windows\\system32")
        with pytest.raises(ValueError, match="Allowed characters"):
            validate_identifier("folder/subfolder")
        with pytest.raises(ValueError, match="Allowed characters"):
            validate_identifier("name with spaces")
        with pytest.raises(ValueError, match="Allowed characters"):
            validate_identifier("id;DROP TABLE sessions;")

    def test_empty_or_non_string_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_identifier("")
        with pytest.raises(ValueError, match="non-empty string"):
            validate_identifier(None)  # type: ignore[arg-type]
