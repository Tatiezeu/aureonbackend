from rest_framework import serializers
from .models import SwitchRequest
from accounts.models import User

class SwitchRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = SwitchRequest
        fields = ['id', 'user', 'user_name', 'user_email', 'requested_role', 'message', 'status', 'created_at']
