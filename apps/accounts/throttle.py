from rest_framework.throttling import AnnonRateThrottle

class ForgetPasswordThrottle(AnnonRateThrottle):
    scope = "forget_password"