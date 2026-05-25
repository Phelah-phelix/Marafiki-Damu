from django.urls import path
from . import views
from .test_views import health_check

urlpatterns = [
    path('health/', health_check, name='health'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('contribute/', views.add_contribution, name='contribute'),
    path('mpesa-payment/', views.mpesa_payment, name='mpesa-payment'),
]
