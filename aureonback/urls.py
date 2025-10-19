from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("email-verification/", include("email_verification.urls")),
    path("password-reset/", include("password_reset.urls")),
    path("phone-verification/", include("phone_verification.urls")),
    path('api/auth/', include('accounts.urls', namespace="accounts")),
    path('api/', include('reports.urls')),
    path('api/profiles/', include('profiles.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
