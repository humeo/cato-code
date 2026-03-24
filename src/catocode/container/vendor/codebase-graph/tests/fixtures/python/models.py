import collections


class Order:
    def __init__(self, items, total):
        self.items = items
        self.total = total

    def validate(self):
        return self.total > 0


class Receipt:
    def __init__(self, order_id, amount):
        self.order_id = order_id
        self.amount = amount


class ReceiptCollection(
    collections.UserList,
):
    pass
