from django.contrib import admin
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, AdminRequest

@admin.register(ChamaGroup)
class ChamaGroupAdmin(admin.ModelAdmin):
    list_display = ['group_name', 'group_code', 'weekly_goal', 'is_active', 'created_at']
    search_fields = ['group_name', 'group_code']
    readonly_fields = ['group_code', 'created_at']

@admin.register(GroupAdmin)
class GroupAdminAdmin(admin.ModelAdmin):
    list_display = ['user', 'managed_group', 'assigned_at']
    search_fields = ['user__username', 'managed_group__group_name']

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'member_number', 'group', 'status', 'is_group_admin', 'total_contributed']
    list_filter = ['status', 'group', 'is_group_admin']
    search_fields = ['user__username', 'phone_number']
    actions = ['approve_members']
    
    def approve_members(self, request, queryset):
        queryset.update(status='approved')
    approve_members.short_description = "Approve selected members"

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'date', 'transaction_id']
    list_filter = ['date', 'payment_method']
    search_fields = ['transaction_id', 'member__user__username']

@admin.register(WeeklyProgress)
class WeeklyProgressAdmin(admin.ModelAdmin):
    list_display = ['member', 'week_start_date', 'total_contributed', 'is_completed']
    list_filter = ['is_completed', 'week_start_date']

@admin.register(AdminRequest)
class AdminRequestAdmin(admin.ModelAdmin):
    list_display = ['requester', 'request_type', 'group_name', 'status', 'created_at']
    list_filter = ['status', 'request_type']
    search_fields = ['requester__username']
