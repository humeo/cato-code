from models import Order


def validate_order(order: Order) -> bool:
    return order.validate()


def format_currency(amount: float) -> str:
    return f"${amount:.2f}"
