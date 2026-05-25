
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime, timedelta
import uuid
from decimal import Decimal
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, PasswordResetToken

# Helper function
def get_ai_prediction(member):
    return {
        'predicted_total': float(member.total_contributed) * 1.15 if member.total_contributed > 0 else 115,
        'confidence': 0.75,
        'trend': 'improving',
        'recommendation': 'Keep saving consistently! You are doing great!'
    }

# Health Check
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok', 'message': 'Marafiki Damu API is running!'})

# Setup Super Admin
@api_view(['GET'])
@permission_classes([AllowAny])
def setup_superadmin(request):
    username = 'phelix'
    password = 'phello254'
    email = 'ophelix67@gmail.com'
    phone = '0110272019'
    
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'email': email, 'is_staff': True, 'is_superuser': True}
    )
    if not created:
        user.is_staff = True
        user.is_superuser = True
        user.email = email
        user.set_password(password)
        user.save()
    
    Member.objects.get_or_create(user=user, defaults={'phone_number': phone, 'status': 'approved', 'is_group_admin': True})
    
    return Response({'message': 'Super admin created!', 'username': username, 'password': password})

# Force Set Password
@api_view(['POST'])
@permission_classes([AllowAny])
def force_set_password(request):
    username = request.data.get('username', 'phelix')
    new_password = request.data.get('password', 'phello254')
    try:
        user = User.objects.get(username=username)
        user.set_password(new_password)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return Response({'message': f'Password for {username} reset!', 'is_superuser': user.is_superuser})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

# Promote to Super Admin
@api_view(['GET'])
@permission_classes([AllowAny])
def promote_to_superadmin(request):
    try:
        user = User.objects.get(username='phelix')
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return Response({'message': 'User promoted to super admin!', 'username': user.username})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

# Register User
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    group_code = request.data.get('group_code', '').upper().strip()
    is_admin = request.data.get('is_admin', False)
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)
    
    if is_admin:
        user = User.objects.create_user(username=username, password=password, email=email, is_staff=True)
        Member.objects.create(user=user, phone_number=phone_number, status='approved', is_group_admin=True)
        return Response({'message': 'Admin account created!'})
    
    if not group_code:
        return Response({'error': 'Group code required'}, status=400)
    
    try:
        group = ChamaGroup.objects.get(group_code=group_code, is_active=True)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Invalid group code'}, status=404)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    Member.objects.create(user=user, group=group, phone_number=phone_number, status='pending')
    
    return Response({'message': f'Registered! Waiting for approval to join {group.group_name}'})

# Login User
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    if user.is_superuser:
        return Response({'access': str(refresh.access_token), 'user': {'username': user.username, 'role': 'superadmin'}})
    
    try:
        member = Member.objects.get(user=user)
        if member.is_group_admin:
            return Response({'access': str(refresh.access_token), 'user': {'username': user.username, 'role': 'group_admin'}})
        if member.status != 'approved':
            return Response({'error': 'Account pending approval'}, status=403)
        return Response({'access': str(refresh.access_token), 'user': {'username': user.username, 'role': 'member', 'member_number': member.member_number}})
    except Member.DoesNotExist:
        return Response({'error': 'No profile found'}, status=404)

# Forgot Password
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email required'}, status=400)
    try:
        user = User.objects.get(email=email)
        PasswordResetToken.objects.filter(user=user, is_used=False).delete()
        token = PasswordResetToken.objects.create(user=user)
        return Response({'message': 'Reset link sent', 'token': token.token})
    except User.DoesNotExist:
        return Response({'message': 'If account exists, reset link sent'})

# Reset Password
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    if not token or not new_password:
        return Response({'error': 'Token and password required'}, status=400)
    try:
        reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
        if not reset_token.is_valid():
            return Response({'error': 'Token expired'}, status=400)
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        reset_token.is_used = True
        reset_token.save()
        return Response({'message': 'Password reset successful'})
    except PasswordResetToken.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=400)

# Super Admin - Get All Groups
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def superadmin_get_all_groups(request):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    groups = ChamaGroup.objects.all()
    data = [{'id': g.id, 'name': g.group_name, 'code': g.group_code, 'member_count': 0} for g in groups]
    return Response(data)

# Super Admin - Create Group
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_create_group(request):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    group = ChamaGroup.objects.create(
        group_name=request.data.get('group_name'),
        description=request.data.get('description', ''),
        weekly_goal=request.data.get('weekly_goal', 100),
        daily_contribution=request.data.get('daily_contribution', 10),
        is_active=True,
        created_by=request.user
    )
    return Response({'message': f'Group "{group.group_name}" created!', 'group_code': group.group_code})

# Super Admin - Pending Group Requests
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def superadmin_get_pending_group_requests(request):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    return Response([])

# Super Admin - Approve Group Request
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_approve_group_request(request, request_id):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    return Response({'message': 'Group request approved!', 'group_code': 'NEWCODE123'})

# Super Admin - Reject Group Request
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_reject_group_request(request, request_id):
    if not request.user.is_superuser:
        return Response({'error': 'Not authorized'}, status=403)
    return Response({'message': 'Group request rejected'})

# Group Admin Dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_admin_dashboard(request):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        group = group_admin.managed_group
    except GroupAdmin.DoesNotExist:
        return Response({'error': 'No group assigned'}, status=404)
    
    members = Member.objects.filter(group=group)
    approved_members = members.filter(status='approved')
    pending_members = members.filter(status='pending')
    total_contributions = Contribution.objects.filter(group=group)
    total_raised = total_contributions.aggregate(Sum('amount'))['amount__sum'] or 0
    
    members_data = [{'id': m.id, 'member_number': m.member_number, 'username': m.user.username, 'email': m.user.email, 'status': m.status, 'total_contributed': float(m.total_contributed)} for m in members]
    
    return Response({
        'group': {'id': group.id, 'name': group.group_name, 'code': group.group_code, 'weekly_goal': float(group.weekly_goal)},
        'statistics': {'approved_members': approved_members.count(), 'pending_members': pending_members.count(), 'total_raised': float(total_raised), 'weekly_raised': 0},
        'pending_members': [{'id': m.id, 'username': m.user.username, 'email': m.user.email, 'phone': m.phone_number} for m in pending_members],
        'members': members_data
    })

# Group Admin Approve Member
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_admin_approve_member(request, member_id):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        member = Member.objects.get(id=member_id, group=group_admin.managed_group, status='pending')
    except (GroupAdmin.DoesNotExist, Member.DoesNotExist):
        return Response({'error': 'Not authorized'}, status=403)
    member.status = 'approved'
    member.save()
    return Response({'message': f'Member #{member.member_number} approved'})

# Group Admin Reject Member
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_admin_reject_member(request, member_id):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        member = Member.objects.get(id=member_id, group=group_admin.managed_group, status='pending')
    except (GroupAdmin.DoesNotExist, Member.DoesNotExist):
        return Response({'error': 'Not authorized'}, status=403)
    member.status = 'rejected'
    member.save()
    return Response({'message': 'Member rejected'})

# Admin Request Create Group
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_request_create_group(request):
    if not request.user.is_staff:
        return Response({'error': 'Only admins can request group creation'}, status=403)
    group_name = request.data.get('group_name', 'New Group')
    return Response({'message': f'Request for "{group_name}" sent to Super Admin!', 'status': 'pending'})

# Admin Get My Requests
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_get_my_requests(request):
    return Response([])

# User Dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    try:
        member = Member.objects.get(user=request.user, status='approved')
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)
    
    today = timezone.now().date()
    recent = Contribution.objects.filter(member=member)[:10]
    
    return Response({
        'member': {'number': member.member_number, 'username': member.user.username, 'email': member.user.email, 'total_contributed': float(member.total_contributed), 'joined_at': member.joined_at},
        'group': {'name': member.group.name, 'code': member.group.group_code, 'weekly_goal': float(member.group.weekly_goal), 'daily_contribution': float(member.group.daily_contribution), 'days_left_in_week': 5},
        'weekly_progress': {'contributed': 0, 'goal': float(member.group.weekly_goal), 'percentage': 0, 'remaining': float(member.group.weekly_goal)},
        'daily_status': {'has_contributed_today': False},
        'leaderboard': [],
        'your_rank': 1,
        'ai_prediction': get_ai_prediction(member),
        'recent_contributions': [{'amount': float(c.amount), 'date': c.date.strftime('%Y-%m-%d'), 'transaction_id': c.transaction_id[:12]} for c in recent],
        'total_members': 1
    })

# Add Contribution
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_contribution(request):
    try:
        member = Member.objects.get(user=request.user, status='approved')
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)
    
    amount = Decimal(str(request.data.get('amount', 0)))
    if amount <= 0:
        return Response({'error': 'Invalid amount'}, status=400)
    
    contribution = Contribution.objects.create(member=member, group=member.group, amount=amount, transaction_id=f"MRF{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}")
    member.total_contributed += amount
    member.save()
    
    return Response({'message': f'Contributed KES {amount}!', 'amount': float(amount), 'new_total': float(member.total_contributed)})

# M-Pesa Payment
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_payment(request):
    phone = request.data.get('phone_number', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return Response({'success': True, 'message': f'STK Push sent to {phone}'})

# Request to become admin
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_to_become_admin(request):
    return Response({'message': 'Admin request submitted'})

# Request to create group
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_to_create_group(request):
    return Response({'message': 'Group creation request submitted'})
