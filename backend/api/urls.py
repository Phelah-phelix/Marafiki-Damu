from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('reset-password/', views.reset_password, name='reset-password'),
    
    # Groups
    path('create-group/', views.create_group, name='create-group'),
    path('my-groups/', views.my_groups, name='my-groups'),
    path('group/<int:group_id>/', views.get_group_detail, name='group-detail'),
    
    # Members
    path('approve-member/<int:member_id>/', views.approve_member, name='approve-member'),
    path('reject-member/<int:member_id>/', views.reject_member, name='reject-member'),
    
    # Contributions
    path('contribute/', views.add_contribution, name='contribute'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('mpesa-payment/', views.mpesa_payment, name='mpesa-payment'),
]
