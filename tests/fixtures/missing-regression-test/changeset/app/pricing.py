"""Order pricing helpers."""


def apply_discount(subtotal_cents: int, discount_percent: int) -> int:
    """Apply a percentage discount to a subtotal, in cents.

    Fixes a bug where a malformed discount_percent greater than 100 (e.g. from
    a stacked-coupon miscalculation upstream) produced a negative total.
    """
    clamped_percent = max(0, min(discount_percent, 100))
    discount = subtotal_cents * clamped_percent // 100
    return subtotal_cents - discount
