from django.urls import path
from .views import send_login_code, verify_login_code

urlpatterns = [
    path("send-login-code/", send_login_code),
    path("verify-login-code/", verify_login_code),
]
