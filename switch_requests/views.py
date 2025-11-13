from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import SwitchRequest
from .serializers import SwitchRequestSerializer
from rest_framework.views import APIView

# User creates a request
class CreateSwitchRequestView(generics.CreateAPIView):
    serializer_class = SwitchRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# Admin view to see all requests
class ListSwitchRequestsView(generics.ListAPIView):
    serializer_class = SwitchRequestSerializer
    queryset = SwitchRequest.objects.all().order_by('-created_at')
    permission_classes = [IsAdminUser]

# Admin resolves a request
class ResolveSwitchRequestView(generics.UpdateAPIView):
    serializer_class = SwitchRequestSerializer
    permission_classes = [IsAdminUser]
    queryset = SwitchRequest.objects.all()

    def update(self, request, *args, **kwargs):
        req = self.get_object()
        req.status = "resolved"
        req.save()
        return Response({"msg": "Request resolved"}, status=status.HTTP_200_OK)

# Admin ignores a request
class IgnoreSwitchRequestView(generics.UpdateAPIView):
    serializer_class = SwitchRequestSerializer
    permission_classes = [IsAdminUser]
    queryset = SwitchRequest.objects.all()

    def update(self, request, *args, **kwargs):
        req = self.get_object()
        req.status = "ignored"
        req.save()
        return Response({"msg": "Request ignored"}, status=status.HTTP_200_OK)
    
# Admin deletes a request  
class DeleteSwitchRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        try:
            req = SwitchRequest.objects.get(id=id)
            req.delete()
            return Response({"message": "Deleted"}, status=200)
        except SwitchRequest.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

