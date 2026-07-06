from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User


class LoginSerializer(TokenObtainPairSerializer):
    username_field = 'login'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'login', 'first_name', 'last_name', 'role', 'school', 'grade', 'subject', 'is_active_for_gamification')
        read_only_fields = ('id', 'login', 'role')


class CreateUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=[User.Role.TEACHER, User.Role.STUDENT])
    grade_id = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=100, required=False, default='')
