"""Authentication service for user login, token validation, and refresh.

This is the primary entry point for all authentication flows.
It coordinates input sanitization, cryptographic verification,
session management, and audit logging.
"""

import time
import logging
from typing import Optional

from demo_repo.auth.crypto import (
    sanitize_input,
    validate_signature,
    hash_password,
    verify_password,
    encode_jwt,
    decode_jwt,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# In-Memory User Store (demo purposes)
# ──────────────────────────────────────────────────────────────────

_USER_STORE = {
    "admin": {
        "password_hash": hash_password("admin123"),
        "roles": ["admin", "user"],
        "email": "admin@samsung-prism.dev",
    },
    "developer": {
        "password_hash": hash_password("dev2026"),
        "roles": ["user"],
        "email": "dev@samsung-prism.dev",
    },
}

# Active session tokens
_ACTIVE_SESSIONS = {}


# ──────────────────────────────────────────────────────────────────
# Token Verification
# ──────────────────────────────────────────────────────────────────

class AuthService:
    """Centralized authentication service handling login, token
    validation, and token refresh operations."""

    def verify_token(self, token: str) -> dict:
        """Validates a JWT authentication token.

        Sanitizes the input, verifies the cryptographic signature,
        checks expiration, and returns the decoded claims.

        Args:
            token: Raw JWT string from the Authorization header.

        Returns:
            Decoded token payload with user claims.

        Raises:
            ValueError: If the token is invalid, expired, or tampered.
        """
        clean_token = sanitize_input(token)
        is_valid = validate_signature(clean_token)

        if not is_valid:
            logger.warning("Token signature validation failed")
            raise ValueError("Invalid authentication token")

        payload = decode_jwt(clean_token)

        # Check if session is still active
        session_id = payload.get("session_id")
        if session_id and session_id not in _ACTIVE_SESSIONS:
            raise ValueError("Session has been revoked")

        logger.info(
            "Token verified for user: %s",
            payload.get("username", "unknown"),
        )

        return payload

    def refresh_token(self, old_token: str) -> str:
        """Refresh an expired or near-expiry token.

        Validates the old token, extracts the claims, and issues
        a new token with a fresh expiration timestamp.

        Args:
            old_token: The current token to refresh.

        Returns:
            New JWT token string with extended expiration.

        Raises:
            ValueError: If the old token cannot be validated.
        """
        clean_token = sanitize_input(old_token)

        # For refresh, we allow slightly expired tokens (grace period)
        try:
            payload = decode_jwt(clean_token)
        except ValueError as e:
            if "expired" in str(e).lower():
                # Allow refresh within 5-minute grace window
                payload = self._decode_with_grace(clean_token, grace_seconds=300)
            else:
                raise

        # Issue new token with same claims but fresh timestamps
        new_payload = {
            "username": payload["username"],
            "roles": payload.get("roles", []),
            "session_id": payload.get("session_id"),
        }

        new_token = encode_jwt(new_payload, expiry_seconds=3600)

        logger.info(
            "Token refreshed for user: %s",
            payload.get("username", "unknown"),
        )

        return new_token

    def _decode_with_grace(self, token: str, grace_seconds: int) -> dict:
        """Attempt to decode a token allowing a grace period for expiration."""
        import base64
        import json

        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Malformed token")

        payload_b64 = parts[0]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)

        if payload.get("exp", 0) + grace_seconds < time.time():
            raise ValueError("Token expired beyond grace period")

        return payload


# ──────────────────────────────────────────────────────────────────
# Login Flow
# ──────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        """Authenticate a user with username and password.

        Sanitizes inputs, verifies credentials against the store,
        creates a session, and returns an access token.

        Args:
            username: The user's login name.
            password: The user's plaintext password.

        Returns:
            Dictionary containing the access token and user info.

        Raises:
            ValueError: If credentials are invalid.
        """
        clean_username = sanitize_input(username)
        clean_password = sanitize_input(password)

        user_record = _USER_STORE.get(clean_username)

        if not user_record:
            log_failed_login(clean_username, reason="user_not_found")
            raise ValueError("Invalid credentials")

        if not verify_password(clean_password, user_record["password_hash"]):
            log_failed_login(clean_username, reason="wrong_password")
            raise ValueError("Invalid credentials")

        # Create session
        session_id = f"sess_{clean_username}_{int(time.time())}"
        _ACTIVE_SESSIONS[session_id] = {
            "username": clean_username,
            "created_at": time.time(),
        }

        # Generate JWT token
        token_payload = {
            "username": clean_username,
            "roles": user_record["roles"],
            "session_id": session_id,
        }
        access_token = encode_jwt(token_payload)

        log_successful_login(clean_username)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "username": clean_username,
                "email": user_record["email"],
                "roles": user_record["roles"],
            },
        }

    def logout(self, token: str) -> bool:
        """Invalidate an active session by revoking the token.

        Args:
            token: The JWT token to revoke.

        Returns:
            True if the session was successfully revoked.
        """
        try:
            payload = self.verify_token(token)
            session_id = payload.get("session_id")
            if session_id and session_id in _ACTIVE_SESSIONS:
                del _ACTIVE_SESSIONS[session_id]
                logger.info("Session revoked: %s", session_id)
                return True
        except ValueError:
            pass
        return False


# ──────────────────────────────────────────────────────────────────
# Audit Logging
# ──────────────────────────────────────────────────────────────────

def log_failed_login(username: str, reason: str) -> None:
    """Record a failed login attempt for security auditing.

    Args:
        username: The attempted username.
        reason: Why the login failed.
    """
    logger.warning(
        "Failed login attempt for '%s': %s at %s",
        username,
        reason,
        time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def log_successful_login(username: str) -> None:
    """Record a successful login for audit trail.

    Args:
        username: The authenticated username.
    """
    logger.info(
        "Successful login for '%s' at %s",
        username,
        time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
