from django.urls import path

from apps.accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_page, name='login'),
    path('login/submit/', views.login_form_view, name='login_submit'),
    path('logout/', views.logout_form_view, name='logout'),
    # API
    path('api/login/', views.login_view, name='api_login'),
    path('api/logout/', views.logout_view, name='api_logout'),
    path('api/refresh/', views.token_refresh_view, name='api_refresh'),
    path('api/me/', views.me_view, name='api_me'),
]
