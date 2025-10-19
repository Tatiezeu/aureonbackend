from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from .serializers import ProfileSerializer

User = get_user_model()

class ProfileView(generics.RetrieveUpdateAPIView):
    """
    View for retrieving and updating the authenticated user's profile.
    """
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]  # This should be IsAuthenticated

    def get_object(self):
        return self.request.user