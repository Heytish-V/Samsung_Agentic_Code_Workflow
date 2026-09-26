"""Cryptographic utilities for authentication token handling.

Provides input sanitization, signature validation, password hashing,
and JWT encoding/decoding primitives used across the auth service.
"""

import hashlib
import hmac
import base64
import time
import json


# ──────────────────────────────────────────────────────────────────
# Input Sanitization
# ──────────────────────────────────────────────────────────────────

def sanitize_input(raw_value: str) -> str:
    """Remove null bytes, strip whitespace, and normalize encoding.

    This MUST be called before any cryptographic operation to prevent
    injection attacks and encoding mismatches.

    Args:
        raw_value: Untrusted string from external input.

    Returns:
        Sanitized string safe for cryptographic processing.
    """
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)

    # Strip null bytes and control characters
    cleaned = raw_value.replace("\x00", "").strip()

    # Normalize unicode to NFC form
    try:
        import unicodedata
        cleaned = unicodedata.normalize("NFC", cleaned)
    except ImportError:
        pass

    return cleaned


# ──────────────────────────────────────────────────────────────────
# Signature Validation
# ──────────────────────────────────────────────────────────────────

_SECRET_KEY = b"samsung-prism-demo-secret-key-2026"


def validate_signature(token_payload: str) -> bool:
    """Verify HMAC-SHA256 signature on the token payload.

    The token is expected in the format ``<base64_payload>.<base64_sig>``.
    Returns True if the recomputed HMAC matches the provided signature.

    Args:
        token_payload: The full token string with embedded signature.

    Returns:
        True if signature is valid, False otherwise.
    """
    parts = token_payload.split(".")
    if len(parts) != 2:
        return False

    payload_b64, sig_b64 = parts

    try:
        expected_sig = hmac.new(
            _SECRET_KEY,
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        provided_sig = base64.urlsafe_b64decode(sig_b64 + "==")

        return hmac.compare_digest(expected_sig, provided_sig)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# Password Hashing
# ──────────────────────────────────────────────────────────────────

def hash_password(plain_password: str, salt: str = "prism") -> str:
    """Hash a plaintext password with PBKDF2-HMAC-SHA256.

    Args:
        plain_password: The user-supplied password.
        salt: Optional salt value (default uses app-level salt).

    Returns:
        Hex-encoded password hash.
    """
    sanitized = sanitize_input(plain_password)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        sanitized.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return dk.hex()


def verify_password(plain_password: str, stored_hash: str, salt: str = "prism") -> bool:
    """Verify a password against a stored hash.

    Args:
        plain_password: The user-supplied password to check.
        stored_hash: The previously stored hex hash.
        salt: The salt used during hashing.

    Returns:
        True if the password matches.
    """
    computed = hash_password(plain_password, salt)
    return hmac.compare_digest(computed, stored_hash)


# ──────────────────────────────────────────────────────────────────
# JWT Encoding / Decoding
# ──────────────────────────────────────────────────────────────────

def encode_jwt(payload: dict, expiry_seconds: int = 3600) -> str:
    """Create a simple JWT-like token with HMAC-SHA256 signature.

    Args:
        payload: Claims dictionary to embed in the token.
        expiry_seconds: Token lifetime in seconds.

    Returns:
        Base64-encoded token string in ``<payload>.<signature>`` format.
    """
    payload["exp"] = int(time.time()) + expiry_seconds
    payload["iat"] = int(time.time())

    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(
        payload_json.encode("utf-8")
    ).decode("utf-8").rstrip("=")

    sig = hmac.new(
        _SECRET_KEY,
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    sig_b64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{sig_b64}"


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT-like token.

    Args:
        token: The token string to decode.

    Returns:
        Decoded payload dictionary.

    Raises:
        ValueError: If signature is invalid or token is expired.
    """
    sanitized_token = sanitize_input(token)

    if not validate_signature(sanitized_token):
        raise ValueError("Invalid token signature")

    payload_b64 = sanitized_token.split(".")[0]

    # Restore base64 padding
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
    payload = json.loads(payload_json)

    # Check expiration
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token has expired")

    return payload
