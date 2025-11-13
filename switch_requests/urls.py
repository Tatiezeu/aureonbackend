from django.urls import path
from .views import (
    CreateSwitchRequestView,
    ListSwitchRequestsView,
    ResolveSwitchRequestView,
    IgnoreSwitchRequestView,
    DeleteSwitchRequestView
)

urlpatterns = [
    path('create/', CreateSwitchRequestView.as_view(), name='create-switch-request'),
    path('all/', ListSwitchRequestsView.as_view(), name='list-switch-requests'),
    path('resolve/<int:pk>/', ResolveSwitchRequestView.as_view(), name='resolve-switch-request'),
    path('ignore/<int:pk>/', IgnoreSwitchRequestView.as_view(), name='ignore-switch-request'),
    path("delete/<int:id>/", DeleteSwitchRequestView.as_view()),

]
