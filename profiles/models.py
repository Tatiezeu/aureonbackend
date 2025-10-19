from django.db import models
from django.conf import settings

# ✅ We don't create a new model here — we just import the User model
User = settings.AUTH_USER_MODEL

# This file can stay empty, or you can add helper functions later.
# Django requires the file to exist, but since we're using the existing User table,
# there's no need for a new Profile model.
