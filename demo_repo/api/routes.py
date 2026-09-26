"""REST API route handlers for the demo application.

Maps HTTP endpoints to service layer functions, handling
request parsing, response formatting, and error handling.
"""

import logging
from typing import Any, Dict

from demo_repo.auth.service import AuthService
from demo_repo.auth.crypto import sanitize_input
from demo_repo.orders.checkout import (
    process_order,
    get_order_history,
    cancel_order,
)
from demo_repo.db.query_executor import fetch_records

logger = logging.getLogger(__name__)

auth_service = AuthService()


# ──────────────────────────────────────────────────────────────────
# Auth Endpoints
# ──────────────────────────────────────────────────────────────────

def handle_login(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST /api/auth/login.

    Args:
        request_body: JSON body with username and password.

    Returns:
        Login response with access token or error.
    """
    try:
        username = sanitize_input(request_body.get("username", ""))
        password = sanitize_input(request_body.get("password", ""))

        result = auth_service.login(username, password)
        return {"status": 200, "data": result}

    except ValueError as e:
        logger.warning("Login failed: %s", e)
        return {"status": 401, "error": str(e)}


def handle_token_refresh(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST /api/auth/refresh.

    Args:
        request_body: JSON body with the current token.

    Returns:
        New token or error.
    """
    try:
        old_token = request_body.get("token", "")
        new_token = auth_service.refresh_token(old_token)
        return {"status": 200, "data": {"access_token": new_token}}

    except ValueError as e:
        return {"status": 401, "error": str(e)}


def handle_logout(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST /api/auth/logout.

    Args:
        request_body: JSON body with the token to revoke.

    Returns:
        Success or failure status.
    """
    token = request_body.get("token", "")
    success = auth_service.logout(token)
    return {"status": 200, "data": {"logged_out": success}}


# ──────────────────────────────────────────────────────────────────
# Order Endpoints
# ──────────────────────────────────────────────────────────────────

def handle_create_order(
    auth_header: str,
    request_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Handle POST /api/orders.

    Args:
        auth_header: Bearer token from Authorization header.
        request_body: JSON body with items and shipping address.

    Returns:
        Order confirmation or error.
    """
    try:
        token = extract_bearer_token(auth_header)
        items = request_body.get("items", [])
        address = request_body.get("shipping_address", "")

        result = process_order(token, items, address)
        return {"status": 201, "data": result}

    except ValueError as e:
        return {"status": 400, "error": str(e)}


def handle_get_orders(auth_header: str) -> Dict[str, Any]:
    """Handle GET /api/orders.

    Args:
        auth_header: Bearer token from Authorization header.

    Returns:
        List of past orders.
    """
    try:
        token = extract_bearer_token(auth_header)
        orders = get_order_history(token)
        return {"status": 200, "data": orders}

    except ValueError as e:
        return {"status": 401, "error": str(e)}


def handle_cancel_order(
    auth_header: str,
    order_id: int,
) -> Dict[str, Any]:
    """Handle DELETE /api/orders/{order_id}.

    Args:
        auth_header: Bearer token from Authorization header.
        order_id: The order to cancel.

    Returns:
        Updated order status.
    """
    try:
        token = extract_bearer_token(auth_header)
        result = cancel_order(token, order_id)
        return {"status": 200, "data": result}

    except ValueError as e:
        return {"status": 400, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# Health & Admin Endpoints
# ──────────────────────────────────────────────────────────────────

def handle_health_check() -> Dict[str, Any]:
    """Handle GET /api/health.

    Returns:
        System health status.
    """
    return {
        "status": 200,
        "data": {
            "healthy": True,
            "service": "samsung-prism-demo",
            "version": "1.0.0",
        },
    }


def handle_admin_users(auth_header: str) -> Dict[str, Any]:
    """Handle GET /api/admin/users (admin-only).

    Args:
        auth_header: Bearer token with admin role.

    Returns:
        User list or authorization error.
    """
    try:
        token = extract_bearer_token(auth_header)
        claims = auth_service.verify_token(token)

        if "admin" not in claims.get("roles", []):
            return {"status": 403, "error": "Admin role required"}

        users = fetch_records("users", limit=50)
        return {"status": 200, "data": users}

    except ValueError as e:
        return {"status": 401, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────────────────────────────

def extract_bearer_token(auth_header: str) -> str:
    """Extract the token from a Bearer authorization header.

    Args:
        auth_header: The full Authorization header value.

    Returns:
        The extracted token string.

    Raises:
        ValueError: If the header format is invalid.
    """
    if not auth_header:
        raise ValueError("Missing Authorization header")

    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Invalid Authorization header format")

    return sanitize_input(parts[1])
