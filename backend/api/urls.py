from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('setup-superadmin/', views.setup_superadmin, name='setup-superadmin'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('reset-password/', views.reset_password, name='reset-password'),
    
    path('superadmin/groups/', views.superadmin_get_all_groups, name='superadmin-groups'),
    path('superadmin/create-group/', views.superadmin_create_group, name='superadmin-create-group'),
    path('superadmin/pending-group-requests/', views.superadmin_get_pending_group_requests, name='superadmin-pending-group-requests'),
    path('superadmin/approve-group-request/<int:request_id>/', views.superadmin_approve_group_request, name='superadmin-approve-group-request'),
    path('superadmin/reject-group-request/<int:request_id>/', views.superadmin_reject_group_request, name='superadmin-reject-group-request'),
    
    path('group-admin/dashboard/', views.group_admin_dashboard, name='group-admin-dashboard'),
    path('group-admin/approve/<int:member_id>/', views.group_admin_approve_member, name='group-admin-approve'),
    path('group-admin/reject/<int:member_id>/', views.group_admin_reject_member, name='group-admin-reject'),
    
    path('admin/request-create-group/', views.admin_request_create_group, name='admin-request-create-group'),
    path('admin/my-requests/', views.admin_get_my_requests, name='admin-my-requests'),
    
    path('dashboard/', views.user_dashboard, name='user-dashboard'),
    path('contribute/', views.add_contribution, name='contribute'),
    path('mpesa-payment/', views.mpesa_payment, name='mpesa-payment'),
    path('request-admin/', views.request_to_become_admin, name='request-admin'),
    path('request-group/', views.request_to_create_group, name='request-group'),
]
    path('force-set-password/', views.force_set_password, name='force-set-password'),
