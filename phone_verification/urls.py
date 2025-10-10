from django.urls import path
from . import views

urlpatterns = [
    path("send-code/", views.SendPhoneCode.as_view(), name="send_phone_code"),
    path("verify-code/", views.VerifyPhoneCode.as_view(), name="verify_phone_code"),
]
