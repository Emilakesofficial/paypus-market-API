class ReviewItemNotFoundError(Exception):
    pass


class OrderNotCompletedError(Exception):
    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__(f"Order is '{current_status}', not completed")


class SelfReviewError(Exception):
    pass


class AlreadyReviewedError(Exception):
    pass