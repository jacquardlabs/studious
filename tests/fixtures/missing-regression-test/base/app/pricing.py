"""Order pricing helpers."""


def apply_discount(subtotal_cents: int, discount_percent: int) -> int:
    """Apply a percentage discount to a subtotal, in cents."""
    discount = subtotal_cents * discount_percent // 100
    return subtotal_cents - discount
