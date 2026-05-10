"""
Unit tests for the ExtensionToken model + helpers.

The token model is small but security-critical: getting hashing wrong or
the format wrong has real consequences. These tests pin down the contract.
"""

from __future__ import annotations

import pytest

from app.models.extension_token import (
    TOKEN_PREFIX,
    generate_token,
    hash_token,
)


class TestGenerate:
    def test_token_has_expected_prefix(self):
        raw, _ = generate_token()
        assert raw.startswith(TOKEN_PREFIX)

    def test_token_has_high_entropy(self):
        """Generated tokens should be unique on every call (no reused fixed seed)."""
        seen = {generate_token()[0] for _ in range(50)}
        assert len(seen) == 50, "Token generator produced duplicates"

    def test_hash_is_64_hex_chars(self):
        """SHA-256 hex is always 64 chars — DB column relies on this."""
        _, h = generate_token()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_deterministic(self):
        """Hashing the same raw token twice gives the same result —
        otherwise lookups by hash would fail."""
        raw, h1 = generate_token()
        h2 = hash_token(raw)
        assert h1 == h2

    def test_different_tokens_have_different_hashes(self):
        raw1, h1 = generate_token()
        raw2, h2 = generate_token()
        assert raw1 != raw2
        assert h1 != h2


class TestHashFunction:
    def test_pure_function_no_state(self):
        """hash_token must be a pure function — same input → same output, no salt."""
        assert hash_token("apex_ext_test") == hash_token("apex_ext_test")

    def test_empty_string_doesnt_crash(self):
        """Edge case — should hash without raising."""
        h = hash_token("")
        assert len(h) == 64

    def test_unicode_input(self):
        """Token validation must work even if someone pastes weird whitespace."""
        h = hash_token("apex_ext_тест")
        assert len(h) == 64
