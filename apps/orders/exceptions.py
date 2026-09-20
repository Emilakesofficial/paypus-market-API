class InsufficientStockError(Exception):
    def __init__(self, product_name):
        self.product_name = product_name
        super().__init__(f"Insufficient stock for {product_name}")


class EmptyCartError(Exception):
    pass