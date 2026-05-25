from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Member

class Command(BaseCommand):
    help = 'Create super admin user'

    def handle(self, *args, **options):
        username = 'phelix'
        password = 'phello254'
        email = 'ophelix67@gmail.com'
        phone = '0110272019'
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        if not created:
            user.is_staff = True
            user.is_superuser = True
            user.email = email
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Updated existing user: {username}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Created new super admin: {username}'))
        
        # Create member profile if not exists
        member, created = Member.objects.get_or_create(
            user=user,
            defaults={
                'phone_number': phone,
                'status': 'approved',
                'is_group_admin': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Member profile created for {username}'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('SUPER ADMIN READY!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Username: phelix')
        self.stdout.write(f'Password: phello254')
        self.stdout.write(f'Email: ophelix67@gmail.com')
        self.stdout.write(f'Phone: 0110272019')
        self.stdout.write('='*50)
