from app.pricing import apply_discount


def test_apply_discount_normal() -> None:
    assert apply_discount(1000, 10) == 900


def test_apply_discount_zero_percent() -> None:
    assert apply_discount(1000, 0) == 1000
