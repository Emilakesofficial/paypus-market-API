from rest_framework.throttling import AnonRateThrottle

class ForgotPasswordThrottle(AnonRateThrottle):
    scope = "forgot_password"