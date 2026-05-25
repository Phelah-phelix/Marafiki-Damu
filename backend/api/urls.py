from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    
    # Super Admin
    path('superadmin/groups/', views.superadmin_get_all_groups, name='superadmin-groups'),
    path('superadmin/pending-requests/', views.superadmin_get_pending_requests, name='superadmin-pending-requests'),
    path('superadmin/approve-request/<int:request_id>/', views.superadmin_approve_request, name='superadmin-approve-request'),
    path('superadmin/reject-request/<int:request_id>/', views.superadmin_reject_request, name='superadmin-reject-request'),
    
    # Admin
    path('admin/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('admin/send-request/', views.admin_send_request, name='admin-send-request'),
    path('admin/my-requests/', views.admin_my_requests, name='admin-my-requests'),
    
    # User
    path('dashboard/', views.user_dashboard, name='user-dashboard'),
    path('contribute/', views.add_contribution, name='contribute'),
]
