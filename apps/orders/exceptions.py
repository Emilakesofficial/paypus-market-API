class InsufficientStockError(Exception):
    def __init__(self, product_name):
        self.product_name = product_name
        super().__init__(f"Insufficient stock for {product_name}")


class EmptyCartError(Exception):
    pass

class OrderNotFoundError(Exception):
    pass


class OrderNotShippableError(Exception):
    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__(f"Order cannot be shipped from status '{current_status}'")


class NothingToShipError(Exception):
    pass

class OrderNotConfirmableError(Exception):
    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__(f"Order cannot be confirmed from status '{current_status}'")