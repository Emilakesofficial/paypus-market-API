from .base import *

DEBUG = os.getenv("DEBUG")
ALLOWED_HOSTS = ["*"]
PAYSTACK_TEST_BANK_ENABLED = True
PAYSTACK_FAKE_TRANSFERS = env.bool("PAYSTACK_FAKE_TRANSFERS", default=True)