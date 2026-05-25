from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from api.models import ChamaGroup, Member, Contribution

class Command(BaseCommand):
    help = 'Setup user groups and permissions for Marafiki Damu'
    
    def handle(self, *args, **options):
        self.stdout.write("Setting up permissions...")
        
        # Create groups
        super_admin_group, _ = Group.objects.get_or_create(name='Super Admin')
        group_admin_group, _ = Group.objects.get_or_create(name='Group Admin')
        member_group, _ = Group.objects.get_or_create(name='Member')
        
        # Get content types
        group_ct = ContentType.objects.get_for_model(ChamaGroup)
        member_ct = ContentType.objects.get_for_model(Member)
        contribution_ct = ContentType.objects.get_for_model(Contribution)
        
        # Super Admin permissions (full access)
        super_permissions = Permission.objects.all()
        super_admin_group.permissions.set(super_permissions)
        
        # Group Admin permissions
        group_admin_permissions = Permission.objects.filter(
            content_type__in=[group_ct, member_ct, contribution_ct],
            codename__in=[
                'view_chamagroup', 'change_chamagroup',
                'view_member', 'change_member', 'add_member',
                'view_contribution', 'add_contribution', 'change_contribution'
            ]
        )
        group_admin_group.permissions.set(group_admin_permissions)
        
        # Member permissions (read-only for their group)
        member_permissions = Permission.objects.filter(
            content_type__in=[member_ct, contribution_ct],
            codename__in=['view_member', 'view_contribution', 'add_contribution']
        )
        member_group.permissions.set(member_permissions)
        
        self.stdout.write(self.style.SUCCESS("✅ Permissions setup complete!"))
        self.stdout.write(f"Groups created:")
        self.stdout.write(f"  - Super Admin: {super_admin_group.permissions.count()} permissions")
        self.stdout.write(f"  - Group Admin: {group_admin_group.permissions.count()} permissions")
        self.stdout.write(f"  - Member: {member_group.permissions.count()} permissions")
