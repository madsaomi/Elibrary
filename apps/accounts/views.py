from django.contrib.auth import login as django_login
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.serializers import LoginSerializer, UserSerializer
from apps.accounts.services import auth_login, auth_logout


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.user
    django_login(request, user)
    refresh = RefreshToken.for_user(user)
    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UserSerializer(user).data,
    })


@api_view(['POST'])
def logout_view(request):
    auth_logout(request)
    return Response({'detail': 'OK'})


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh_view(request):
    from rest_framework_simplejwt.views import TokenRefreshView
    return TokenRefreshView.as_view()(request)


@api_view(['GET'])
def me_view(request):
    return Response(UserSerializer(request.user).data)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'accounts/login.html')


@require_POST
def login_form_view(request):
    login = request.POST.get('login')
    password = request.POST.get('password')
    user = auth_login(request, login, password)
    if user is None:
        return render(request, 'accounts/login.html', {'error': _('Неверный логин или пароль')})
    return redirect('dashboard:home')


@require_POST
def logout_form_view(request):
    auth_logout(request)
    return redirect('accounts:login')
