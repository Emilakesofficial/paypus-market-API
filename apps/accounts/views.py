from rest_framework import generics, permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from apps.accounts.serializers import RegisterSerializer, LogoutSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from apps.accounts.throttle import ForgotPasswordThrottle
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.accounts.utils import (
    MAX_OTP_ATTEMPTS,
    OTP_TTL_SECONDS,
    attempts_cache_key,
    generate_otp,
    hash_otp,
    otp_cache_key,
    send_otp_email,
)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ForgotPasswordThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email=email).first()
        if user:
            otp = generate_otp()
            cache.set(otp_cache_key(email), hash_otp(otp), timeout=OTP_TTL_SECONDS)
            cache.set(attempts_cache_key(email), 0, timeout=OTP_TTL_SECONDS)
            send_otp_email(email, otp)

        # Same response whether or not the email exists — don't leak
        # which addresses are registered.
        return Response(
            {"detail": "If that email is registered, a reset code has been sent."},
            status=status.HTTP_200_OK,
        )
        
class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        attempts = cache.get(attempts_cache_key(email))
        if attempts is not None and attempts >= MAX_OTP_ATTEMPTS:
            return Response(
                {"detail": "Too many failed attempts. Request a new code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        stored_hash = cache.get(otp_cache_key(email))
        if stored_hash is None:
            return Response(
                {"detail": "Code expired or not found. Request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hash_otp(otp) != stored_hash:
            cache.set(attempts_cache_key(email), (attempts or 0) + 1, timeout=OTP_TTL_SECONDS)
            return Response({"detail": "Incorrect code."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "Invalid request."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password) # hash the password before saving
        user.save()
        cache.delete(otp_cache_key(email))
        cache.delete(attempts_cache_key(email))
        return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)

class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh_token"])
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(status=status.HTTP_205_RESET_CONTENT)