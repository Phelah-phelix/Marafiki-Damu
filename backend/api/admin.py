from django.contrib import admin
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, PasswordResetToken, AI_Prediction

@admin.register(ChamaGroup)
class ChamaGroupAdmin(admin.ModelAdmin):
    list_display = ['group_name', 'group_code', 'is_active', 'created_at']
    search_fields = ['group_name', 'group_code']
    readonly_fields = ['group_code', 'created_at']

@admin.register(GroupAdmin)
class GroupAdminAdmin(admin.ModelAdmin):
    list_display = ['user', 'managed_group', 'created_at']
    search_fields = ['user__username', 'managed_group__group_name']

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'member_number', 'group', 'status', 'total_contributed']
    list_filter = ['status', 'group']
    search_fields = ['user__username', 'phone_number']
    actions = ['approve_members']
    
    def approve_members(self, request, queryset):
        queryset.update(status='approved')
    approve_members.short_description = "Approve selected members"

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'date', 'transaction_id']
    list_filter = ['date']
    search_fields = ['transaction_id', 'member__user__username']

@admin.register(WeeklyProgress)
class WeeklyProgressAdmin(admin.ModelAdmin):
    list_display = ['member', 'week_start_date', 'total_contributed', 'is_completed']

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'expires_at', 'is_used']

@admin.register(AI_Prediction)
class AIPredictionAdmin(admin.ModelAdmin):
    list_display = ['member', 'prediction_date', 'trend', 'confidence_score']
