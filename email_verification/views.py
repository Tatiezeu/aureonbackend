import random
import json
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache


@csrf_exempt
def send_login_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")

        if not email:
            return JsonResponse({"error": "Email is required"}, status=400)

        # Generate a random 4-digit code
        code = str(random.randint(1000, 9999))

        # Store code in cache for 5 minutes
        cache.set(f"login_code_{email}", code, timeout=300)

        # Send the verification email
        send_mail(
            subject="Your Aureon Verification Code",
            message=f"Hello,\n\nYour verification code is: {code}\nIt expires in 5 minutes.",
            from_email="tatiezeub@gmail.com",
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({"message": "Verification code sent successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def verify_login_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")
        code = data.get("code")

        if not email or not code:
            return JsonResponse({"error": "Email and code required"}, status=400)

        stored_code = cache.get(f"login_code_{email}")

        if stored_code is None:
            return JsonResponse({"error": "Code expired or not sent"}, status=400)

        if stored_code == code:
            return JsonResponse({"verified": True})
        else:
            return JsonResponse({"verified": False}, status=400)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
