from django.urls import path
from .views import ChatBotAPIView

urlpatterns = [
    path("ask/", ChatBotAPIView.as_view(), name="chatbot-ask"),
]
