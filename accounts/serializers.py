from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if user.status == 'suspended':
            raise serializers.ValidationError("Account suspended")
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'status': user.status,
            'phone': user.phone,
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
        }
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'role', 'status', 'profile_picture','is_active']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone', 'role', 'status', 'profile_picture']

    def create(self, validated_data):
        # Pop profile_picture if it exists
        profile_picture = validated_data.pop('profile_picture', None)

        # Create user with remaining fields
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            username=validated_data.get('username', ''),
            phone=validated_data.get('phone', ''),
            role=validated_data.get('role', 'accountant'),
            status=validated_data.get('status', 'active'),
        )

        # Assign profile picture if provided
        if profile_picture:
            user.profile_picture = profile_picture
            user.save()

        return user
