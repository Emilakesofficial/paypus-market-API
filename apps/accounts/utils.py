import hashlib
import random

from django.conf import settings
from django.core.mail import send_mail

OTP_TTL_SECONDS = 600  # 10 minutes
MAX_OTP_ATTEMPTS = 5


def generate_otp():
    return f"{random.randint(0, 999999):06d}"


def hash_otp(otp):
    # Never store the raw OTP anywhere, including in Redis.
    return hashlib.sha256(otp.encode()).hexdigest()


def otp_cache_key(email):
    return f"pwreset:otp:{email}"


def attempts_cache_key(email):
    return f"pwreset:attempts:{email}"


def send_otp_email(email, otp):
    send_mail(
        subject="Your Paypus password reset code",
        message=f"Your one-time password reset code is: {otp}\nThis code expires in 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )