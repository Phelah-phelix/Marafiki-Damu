from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Member

@api_view(['GET'])
@permission_classes([AllowAny])
def setup_superadmin(request):
    """One-time endpoint to create super admin"""
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
    
    Member.objects.get_or_create(
        user=user,
        defaults={
            'phone_number': phone,
            'status': 'approved',
            'is_group_admin': True
        }
    )
    
    return Response({
        'message': 'Super admin created!',
        'username': username,
        'password': password,
        'email': email
    })
