from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from twilio.rest import Client
from django.conf import settings
import random
import re

# In-memory store for OTPs (for demo purposes)
# Replace with database or cache in production
otp_store = {}

class SendPhoneCode(APIView):
    def post(self, request, *args, **kwargs):
        print("📩 Received request data:", request.data)  # Debug log

        phone_number = request.data.get("phone_number")

        if not phone_number:
            print("⚠️ Phone number missing in request")
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate phone number format (basic E.164 check)
        if not re.match(r"^\+\d{10,15}$", phone_number):
            print(f"⚠️ Invalid phone number format: {phone_number}")
            return Response({
                "error": "Invalid phone number format. Must be in E.164 format (e.g., +2376XXXXXXXX)."
            }, status=status.HTTP_400_BAD_REQUEST)

        otp_code = str(random.randint(1000, 9999))
        otp_store[phone_number] = otp_code  # Store OTP temporarily
        print(f"🔢 Generated OTP: {otp_code} for {phone_number}")

        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            print(f"📞 Sending SMS to {phone_number}...")
            message = client.messages.create(
                body=f"📱 Your Aureon verification code is: {otp_code}",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )

            print(f"✅ OTP sent successfully. Twilio SID: {message.sid}")

            return Response({
                "message": "OTP sent successfully",
                "otp": otp_code,  # For demo/testing only
                "twilio_sid": message.sid
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ Twilio error:", e)
            return Response({
                "error": "Twilio failed to send message",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyPhoneCode(APIView):
    def post(self, request, *args, **kwargs):
        print("📩 Received verification request:", request.data)

        phone_number = request.data.get("phone_number")
        code = request.data.get("code")

        if not phone_number or not code:
            print("⚠️ Missing phone number or code")
            return Response({"error": "Phone number and code are required"}, status=status.HTTP_400_BAD_REQUEST)

        stored_code = otp_store.get(phone_number)
        print(f"🔍 Stored OTP for {phone_number}: {stored_code}, received code: {code}")

        if stored_code == code:
            del otp_store[phone_number]  # Remove after successful verification
            print(f"✅ OTP verified successfully for {phone_number}")
            return Response({"verified": True, "message": "OTP verified successfully"}, status=status.HTTP_200_OK)

        print(f"❌ Invalid OTP for {phone_number}")
        return Response({"verified": False, "message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
