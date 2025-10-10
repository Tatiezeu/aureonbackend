import secrets
import json
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from accounts.models import User
from .models import PasswordResetToken


@csrf_exempt
def forgot_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")
        if not email:
            return JsonResponse({"error": "Email is required"}, status=400)

        user = User.objects.filter(email=email).first()
        if not user:
            return JsonResponse({"error": "Email not found"}, status=404)

        token = secrets.token_urlsafe(50)
        expires_at = timezone.now() + timedelta(hours=1)

        PasswordResetToken.objects.create(user=user, token=token, expires_at=expires_at)

        # 🔹 DEEP LINK for mobile app
        reset_link = f"myapp://reset-password?token={token}"

        send_mail(
            subject="Reset Your Aureon Password",
            message=f"Hello {user.email},\n\nClick below to reset your password:\n{reset_link}\n\nThis link expires in 1 hour.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({"message": "Password reset email sent successfully"})

    except Exception as e:
        import traceback
        print("❌ ERROR in forgot_password:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def reset_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
        token = data.get("token")
        new_password = data.get("password")

        if not token or not new_password:
            return JsonResponse({"error": "Token and new password required"}, status=400)

        token_obj = PasswordResetToken.objects.filter(token=token).first()
        if not token_obj or token_obj.is_expired():
            return JsonResponse({"error": "Invalid or expired token"}, status=400)

        user = token_obj.user
        user.set_password(new_password)
        user.save()

        token_obj.delete()

        return JsonResponse({"message": "Password reset successful"})

    except Exception as e:
        import traceback
        print("❌ ERROR in reset_password:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)
