from models import Order, Receipt
from utils import validate_order, format_currency


def process_payment(
    order: Order,
) -> Receipt:
    if not validate_order(order):
        raise ValueError("Invalid order")
    amount = order.total
    formatted = format_currency(amount)
    print(f"Processing {formatted}")
    return Receipt(order_id=1, amount=amount)


class PaymentProcessor:
    def __init__(self):
        self.processed = []

    def run(self, order: Order) -> Receipt:
        receipt = process_payment(order)
        self.processed.append(receipt)
        return receipt
