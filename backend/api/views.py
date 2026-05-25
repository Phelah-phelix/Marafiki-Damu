from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from decimal import Decimal
import uuid
from .models import ChamaGroup, GroupAdmin, Member, Contribution, GroupCreationRequest

# Health check
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok', 'message': 'API is running'})

# Register
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone = request.data.get('phone_number', '')
    is_admin = request.data.get('is_admin', False)
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username exists'}, status=400)
    
    if is_admin:
        user = User.objects.create_user(username=username, password=password, email=email, is_staff=True)
        Member.objects.create(user=user, phone_number=phone, status='approved', is_group_admin=True)
        return Response({'message': 'Admin created! You can now login.'})
    
    return Response({'message': 'User registration requires group code'})

# Login
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    role = 'user'
    if user.is_superuser:
        role = 'superadmin'
    elif user.is_staff:
        role = 'admin'
    
    return Response({
        'access': str(refresh.access_token),
        'user': {'id': user.id, 'username': user.username, 'role': role}
    })

# ============ SUPER ADMIN ENDPOINTS ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def superadmin_get_all_groups(request):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    groups = ChamaGroup.objects.all()
    data = [{'id': g.id, 'name': g.group_name, 'code': g.group_code, 'member_count': 0} for g in groups]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def superadmin_get_pending_requests(request):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    requests = GroupCreationRequest.objects.filter(status='pending')
    data = [{
        'id': r.id,
        'requester': r.requester.username,
        'requester_email': r.requester.email,
        'group_name': r.group_name,
        'weekly_goal': float(r.weekly_goal),
        'daily_contribution': float(r.daily_contribution),
        'admin_notes': r.admin_notes,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in requests]
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_approve_request(request, request_id):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    
    try:
        req = GroupCreationRequest.objects.get(id=request_id, status='pending')
    except GroupCreationRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)
    
    group = ChamaGroup.objects.create(
        group_name=req.group_name,
        description=req.description,
        weekly_goal=req.weekly_goal,
        daily_contribution=req.daily_contribution,
        is_active=True
    )
    
    req.status = 'approved'
    req.superadmin_notes = request.data.get('notes', '')
    req.save()
    
    req.requester.is_staff = True
    req.requester.save()
    
    GroupAdmin.objects.get_or_create(user=req.requester, defaults={'managed_group': group})
    
    return Response({'message': f'Group "{group.group_name}" approved! Code: {group.group_code}', 'group_code': group.group_code})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_reject_request(request, request_id):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    
    try:
        req = GroupCreationRequest.objects.get(id=request_id, status='pending')
    except GroupCreationRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)
    
    req.status = 'rejected'
    req.superadmin_notes = request.data.get('notes', '')
    req.save()
    
    return Response({'message': 'Request rejected'})

# ============ ADMIN ENDPOINTS ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        group = group_admin.managed_group
        return Response({
            'group': {
                'name': group.group_name,
                'code': group.group_code
            }
        })
    except GroupAdmin.DoesNotExist:
        return Response({'group': None})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_send_request(request):
    print("=" * 50)
    print("ADMIN SEND REQUEST CALLED")
    print("User:", request.user.username)
    print("Is staff:", request.user.is_staff)
    print("Request data:", request.data)
    print("=" * 50)
    
    if not request.user.is_staff and not request.user.is_superuser:
        return Response({'error': 'Only admins can send requests'}, status=403)
    
    group_name = request.data.get('group_name')
    if not group_name:
        return Response({'error': 'Group name is required'}, status=400)
    
    try:
        group_request = GroupCreationRequest.objects.create(
            requester=request.user,
            group_name=group_name,
            description=request.data.get('description', ''),
            weekly_goal=request.data.get('weekly_goal', 100),
            daily_contribution=request.data.get('daily_contribution', 10),
            admin_notes=request.data.get('admin_notes', ''),
            status='pending'
        )
        
        print(f"✅ Request created with ID: {group_request.id}")
        
        return Response({
            'success': True,
            'message': f'Request for "{group_name}" sent to Super Admin!',
            'request_id': group_request.id
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_my_requests(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    
    requests = GroupCreationRequest.objects.filter(requester=request.user)
    data = [{
        'id': r.id,
        'group_name': r.group_name,
        'weekly_goal': float(r.weekly_goal),
        'daily_contribution': float(r.daily_contribution),
        'status': r.status,
        'superadmin_notes': r.superadmin_notes,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in requests]
    return Response(data)

# ============ USER ENDPOINTS ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    return Response({'message': 'User dashboard'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_contribution(request):
    return Response({'message': 'Contribution added'})
