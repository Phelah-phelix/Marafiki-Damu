from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser

class IsGroupAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        from .models import GroupAdmin
        return GroupAdmin.objects.filter(user=request.user).exists()

class IsGroupMember(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        from .models import Member
        try:
            member = Member.objects.get(user=request.user)
            return member.status == 'approved'
        except:
            return False
