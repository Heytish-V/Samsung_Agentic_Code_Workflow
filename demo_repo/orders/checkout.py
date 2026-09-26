"""Order checkout service coordinating auth, payment, and database.

This module demonstrates cross-file call chains:
    verify_token -> execute_query -> send_notification

showing how the agentic system traces calls across module boundaries.
"""

import time
import logging
from typing import Any, Dict, List, Optional

from demo_repo.auth.service import AuthService
from demo_repo.auth.crypto import sanitize_input
from demo_repo.db.query_executor import execute_query, insert_record, fetch_records
from demo_repo.db.connection import connect_db

logger = logging.getLogger(__name__)

auth_service = AuthService()


# ──────────────────────────────────────────────────────────────────
# Order Processing
# ──────────────────────────────────────────────────────────────────

def process_order(
    token: str,
    items: List[Dict[str, Any]],
    shipping_address: str,
) -> Dict[str, Any]:
    """Process a complete order from cart to confirmation.

    Coordinates the full checkout flow:
    1. Verify user authentication token
    2. Validate and sanitize order items
    3. Calculate totals
    4. Insert order record into database
    5. Send confirmation notification

    Args:
        token: JWT authentication token.
        items: List of order items with product_id and quantity.
        shipping_address: Delivery address.

    Returns:
        Order confirmation with order ID and status.

    Raises:
        ValueError: If authentication fails or items are invalid.
    """
    # Step 1: Authenticate
    user_claims = auth_service.verify_token(token)
    username = user_claims.get("username", "unknown")

    # Step 2: Sanitize and validate items
    validated_items = validate_order_items(items)
    clean_address = sanitize_input(shipping_address)

    # Step 3: Calculate totals
    subtotal = calculate_subtotal(validated_items)
    tax = calculate_tax(subtotal)
    total = subtotal + tax

    # Step 4: Persist to database
    order_data = {
        "username": username,
        "items": str(validated_items),
        "shipping_address": clean_address,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "status": "confirmed",
    }
    order_record = insert_record("orders", order_data)

    # Step 5: Send confirmation
    send_order_notification(username, order_record.get("id", 0))

    logger.info("Order processed for %s: total=%.2f", username, total)

    return {
        "order_id": order_record.get("id"),
        "status": "confirmed",
        "total": total,
        "items_count": len(validated_items),
    }


def get_order_history(
    token: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve order history for the authenticated user.

    Args:
        token: JWT authentication token.
        limit: Maximum number of orders to return.

    Returns:
        List of past orders for the user.
    """
    user_claims = auth_service.verify_token(token)
    username = user_claims.get("username")

    orders = fetch_records(
        "orders",
        conditions={"username": username},
        limit=limit,
    )

    return orders


def cancel_order(
    token: str,
    order_id: int,
) -> Dict[str, Any]:
    """Cancel an existing order.

    Args:
        token: JWT authentication token.
        order_id: The ID of the order to cancel.

    Returns:
        Updated order status.

    Raises:
        ValueError: If order doesn't exist or can't be cancelled.
    """
    user_claims = auth_service.verify_token(token)
    username = user_claims.get("username")

    # Verify order belongs to user
    orders = fetch_records(
        "orders",
        conditions={"id": order_id, "username": username},
    )

    if not orders:
        raise ValueError(f"Order {order_id} not found for user {username}")

    # Update order status
    result = execute_query(
        "UPDATE orders SET status = :status WHERE id = :id RETURNING *",
        params={"status": "cancelled", "id": order_id},
    )

    send_cancellation_notification(username, order_id)

    return result[0] if result else {}


# ──────────────────────────────────────────────────────────────────
# Order Validation & Calculation
# ──────────────────────────────────────────────────────────────────

def validate_order_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and sanitize order items.

    Args:
        items: Raw order items from the client.

    Returns:
        Validated and sanitized items.

    Raises:
        ValueError: If any item is invalid.
    """
    if not items:
        raise ValueError("Order must contain at least one item")

    validated = []
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)

        if not product_id:
            raise ValueError("Each item must have a product_id")

        if not isinstance(quantity, int) or quantity < 1:
            raise ValueError(f"Invalid quantity for product {product_id}")

        clean_name = sanitize_input(str(item.get("name", f"Product {product_id}")))

        validated.append({
            "product_id": product_id,
            "quantity": quantity,
            "name": clean_name,
            "unit_price": item.get("unit_price", 9.99),
        })

    return validated


def calculate_subtotal(items: List[Dict[str, Any]]) -> float:
    """Calculate the order subtotal before tax.

    Args:
        items: Validated order items.

    Returns:
        Subtotal amount.
    """
    total = 0.0
    for item in items:
        total += item["unit_price"] * item["quantity"]
    return round(total, 2)


def calculate_tax(subtotal: float, rate: float = 0.08) -> float:
    """Calculate tax amount on the subtotal.

    Args:
        subtotal: The pre-tax amount.
        rate: Tax rate (default 8%).

    Returns:
        Tax amount.
    """
    return round(subtotal * rate, 2)


# ──────────────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────────────

def send_order_notification(username: str, order_id: int) -> None:
    """Send an order confirmation notification to the user.

    Args:
        username: The user who placed the order.
        order_id: The confirmed order ID.
    """
    logger.info(
        "Notification sent to %s: Order #%d confirmed",
        username,
        order_id,
    )


def send_cancellation_notification(username: str, order_id: int) -> None:
    """Send an order cancellation notification.

    Args:
        username: The user who cancelled.
        order_id: The cancelled order ID.
    """
    logger.info(
        "Cancellation notification sent to %s: Order #%d",
        username,
        order_id,
    )
