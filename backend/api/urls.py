from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('reset-password/', views.reset_password, name='reset-password'),
    
    path('superadmin/groups/', views.superadmin_get_all_groups, name='superadmin-groups'),
    path('superadmin/create-group/', views.superadmin_create_group, name='superadmin-create-group'),
    path('superadmin/assign-admin/', views.superadmin_assign_group_admin, name='superadmin-assign-admin'),
    path('superadmin/approve-member/<int:member_id>/', views.superadmin_approve_member, name='superadmin-approve-member'),
    path('superadmin/pending-requests/', views.superadmin_get_pending_requests, name='superadmin-pending-requests'),
    path('superadmin/approve-request/<int:request_id>/', views.superadmin_approve_admin_request, name='superadmin-approve-request'),
    path('superadmin/reject-request/<int:request_id>/', views.superadmin_reject_request, name='superadmin-reject-request'),
    
    path('group-admin/dashboard/', views.group_admin_dashboard, name='group-admin-dashboard'),
    path('group-admin/approve/<int:member_id>/', views.group_admin_approve_member, name='group-admin-approve'),
    path('group-admin/reject/<int:member_id>/', views.group_admin_reject_member, name='group-admin-reject'),
    path('group-admin/settings/', views.group_admin_update_settings, name='group-admin-settings'),
    
    path('dashboard/', views.user_dashboard, name='user-dashboard'),
    path('contribute/', views.add_contribution, name='contribute'),
    path('mpesa-payment/', views.mpesa_payment, name='mpesa-payment'),
    path('request-admin/', views.request_to_become_admin, name='request-admin'),
    path('request-group/', views.request_to_create_group, name='request-group'),
]
path('setup-superadmin/', views.setup_superadmin, name='setup-superadmin'),
