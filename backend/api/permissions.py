from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """
    Permission class for Super Admin only.
    Super Admin has full system access.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsGroupAdmin(permissions.BasePermission):
    """
    Permission class for Group Admin.
    Group Admin can only access their assigned group.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admin has all permissions
        if request.user.is_superuser:
            return True
        
        # Check if user is a group admin
        from .models import GroupAdmin
        return GroupAdmin.objects.filter(user=request.user).exists()
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admin can access everything
        if request.user.is_superuser:
            return True
        
        from .models import GroupAdmin, Member
        
        try:
            group_admin = GroupAdmin.objects.get(user=request.user)
            managed_group = group_admin.managed_group
            
            # Check if the object belongs to the admin's group
            if hasattr(obj, 'group'):
                return obj.group == managed_group
            elif hasattr(obj, 'managed_group'):
                return obj.managed_group == managed_group
            elif hasattr(obj, 'member') and hasattr(obj.member, 'group'):
                return obj.member.group == managed_group
            elif hasattr(obj, 'user') and hasattr(obj.user, 'member_profile'):
                return obj.user.member_profile.group == managed_group
        except:
            pass
        
        return False


class IsGroupMember(permissions.BasePermission):
    """
    Permission class for Regular Group Members.
    Members can only access their own data and their group's data.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admin has all permissions
        if request.user.is_superuser:
            return True
        
        # Check if user is a regular member
        from .models import Member
        try:
            member = Member.objects.get(user=request.user)
            return member.status == 'approved'
        except:
            return False
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Super admin can access everything
        if request.user.is_superuser:
            return True
        
        from .models import Member
        
        try:
            member = Member.objects.get(user=request.user)
            
            # User can access their own data
            if hasattr(obj, 'user') and obj.user == request.user:
                return True
            if hasattr(obj, 'member') and obj.member == member:
                return True
            
            # User can access their group's data
            if hasattr(obj, 'group') and obj.group == member.group:
                return True
            if hasattr(obj, 'member') and obj.member.group == member.group:
                return True
                
        except:
            pass
        
        return False


class CanCreateGroup(permissions.BasePermission):
    """
    Permission for creating groups.
    Only Super Admin can create groups.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class CanApproveMembers(permissions.BasePermission):
    """
    Permission for approving members.
    Super Admin and Group Admin can approve members.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        from .models import GroupAdmin
        return GroupAdmin.objects.filter(user=request.user).exists()
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        from .models import GroupAdmin
        
        try:
            group_admin = GroupAdmin.objects.get(user=request.user)
            # Check if the member belongs to the admin's group
            if hasattr(obj, 'group'):
                return obj.group == group_admin.managed_group
            elif hasattr(obj, 'member') and hasattr(obj.member, 'group'):
                return obj.member.group == group_admin.managed_group
        except:
            pass
        
        return False
