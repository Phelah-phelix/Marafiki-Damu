from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime, timedelta
import uuid
import json
from decimal import Decimal
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, AdminRequest, PasswordResetToken
from .permissions import IsSuperAdmin, IsGroupAdmin, IsGroupMember
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
# ==================== AUTHENTICATION VIEWS ====================
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
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    if is_admin:
        user = User.objects.create_user(username=username, password=password, email=email, is_staff=True)
        member = Member.objects.create(user=user, phone_number=phone_number, status='approved', is_group_admin=True)
        return Response({'message': 'Admin account created!', 'user_id': user.id}, status=status.HTTP_201_CREATED)
    
    if not group_code:
        return Response({'error': 'Group code required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        group = ChamaGroup.objects.get(group_code=group_code, is_active=True)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Invalid group code'}, status=status.HTTP_404_NOT_FOUND)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    member = Member.objects.create(user=user, group=group, phone_number=phone_number, status='pending')
    
    return Response({'message': f'Registered! Waiting for approval to join {group.group_name}'})
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    if user.is_superuser:
        return Response({'access': str(refresh.access_token), 'user': {'id': user.id, 'username': user.username, 'role': 'superadmin'}})
    
    try:
        member = Member.objects.get(user=user)
        if member.is_group_admin:
            return Response({'access': str(refresh.access_token), 'user': {'id': user.id, 'username': user.username, 'role': 'group_admin'}})
        if member.status != 'approved':
            return Response({'error': 'Account pending approval'}, status=status.HTTP_403_FORBIDDEN)
        return Response({'access': str(refresh.access_token), 'user': {'id': user.id, 'username': user.username, 'role': 'member', 'member_number': member.member_number}})
    except Member.DoesNotExist:
        return Response({'error': 'No profile found'}, status=status.HTTP_404_NOT_FOUND)
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email=email)
        PasswordResetToken.objects.filter(user=user, is_used=False).delete()
        token = PasswordResetToken.objects.create(user=user)
        return Response({'message': 'Reset link sent', 'token': token.token})
    except User.DoesNotExist:
        return Response({'message': 'If account exists, reset link sent'})
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    if not token or not new_password:
        return Response({'error': 'Token and password required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
        if not reset_token.is_valid():
            return Response({'error': 'Token expired'}, status=status.HTTP_400_BAD_REQUEST)
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        reset_token.is_used = True
        reset_token.save()
        return Response({'message': 'Password reset successful'})
    except PasswordResetToken.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
# ==================== SUPER ADMIN VIEWS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_get_all_groups(request):
    groups = ChamaGroup.objects.all().order_by('-created_at')
    data = []
    for group in groups:
        admin = GroupAdmin.objects.filter(managed_group=group).first()
        data.append({
            'id': group.id, 'name': group.group_name, 'code': group.group_code,
            'description': group.description, 'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution),
            'member_count': Member.objects.filter(group=group, status='approved').count(),
            'pending_count': Member.objects.filter(group=group, status='pending').count(),
            'admin_name': admin.user.username if admin else 'No admin',
            'is_active': group.is_active
        })
    return Response(data)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_create_group(request):
    group = ChamaGroup.objects.create(
        group_name=request.data.get('group_name'),
        description=request.data.get('description', ''),
        weekly_goal=request.data.get('weekly_goal', 100),
        daily_contribution=request.data.get('daily_contribution', 10),
        max_members=request.data.get('max_members', 50),
        is_active=True, created_by=request.user
    )
    return Response({'message': f'Group "{group.group_name}" created!', 'group_code': group.group_code, 'group_id': group.id})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_assign_group_admin(request):
    try:
        user = User.objects.get(username=request.data.get('username'))
        group = ChamaGroup.objects.get(id=request.data.get('group_id'))
    except (User.DoesNotExist, ChamaGroup.DoesNotExist):
        return Response({'error': 'User or group not found'}, status=status.HTTP_404_NOT_FOUND)
    user.is_staff = True
    user.save()
    group_admin, _ = GroupAdmin.objects.get_or_create(user=user, defaults={'managed_group': group, 'assigned_by': request.user})
    if not _:
        group_admin.managed_group = group
        group_admin.save()
    return Response({'message': f'{user.username} is now admin of {group.group_name}', 'group_code': group.group_code})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_approve_member(request, member_id):
    try:
        member = Member.objects.get(id=member_id, status='pending')
    except Member.DoesNotExist:
        return Response({'error': 'Pending member not found'}, status=status.HTTP_404_NOT_FOUND)
    member.status = 'approved'
    member.approved_by = request.user
    member.save()
    return Response({'message': f'Member #{member.member_number} approved'})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_get_pending_requests(request):
    requests = AdminRequest.objects.filter(status='pending')
    data = [{'id': r.id, 'requester': r.requester.username, 'requester_email': r.requester.email, 'request_type': r.request_type, 'group_name': r.group_name, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')} for r in requests]
    return Response(data)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_approve_admin_request(request, request_id):
    try:
        admin_request = AdminRequest.objects.get(id=request_id, status='pending')
    except AdminRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
    group = ChamaGroup.objects.first()
    if not group:
        group = ChamaGroup.objects.create(group_name='Default Group', weekly_goal=100, daily_contribution=10)
    user = admin_request.requester
    user.is_staff = True
    user.save()
    GroupAdmin.objects.create(user=user, managed_group=group, assigned_by=request.user)
    admin_request.status = 'approved'
    admin_request.reviewed_by = request.user
    admin_request.reviewed_at = timezone.now()
    admin_request.save()
    return Response({'message': f'Admin request approved for {user.username}', 'group_code': group.group_code})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_reject_request(request, request_id):
    try:
        admin_request = AdminRequest.objects.get(id=request_id, status='pending')
    except AdminRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
    admin_request.status = 'rejected'
    admin_request.reviewed_by = request.user
    admin_request.reviewed_at = timezone.now()
    admin_request.save()
    return Response({'message': 'Request rejected'})
# ==================== GROUP ADMIN VIEWS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_admin_dashboard(request):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        group = group_admin.managed_group
    except GroupAdmin.DoesNotExist:
        return Response({'error': 'Not a group admin'}, status=status.HTTP_403_FORBIDDEN)
    
    members = Member.objects.filter(group=group)
    pending_members = members.filter(status='pending')
    approved_members = members.filter(status='approved')
    total_contributions = Contribution.objects.filter(group=group)
    total_raised = total_contributions.aggregate(Sum('amount'))['amount__sum'] or 0
    this_week = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
    weekly_contributions = total_contributions.filter(date__gte=this_week)
    weekly_total = weekly_contributions.aggregate(Sum('amount'))['amount__sum'] or 0
    
    members_data = [{'id': m.id, 'member_number': m.member_number, 'username': m.user.username, 'email': m.user.email, 'phone': m.phone_number, 'status': m.status, 'total_contributed': float(m.total_contributed)} for m in members]
    
    return Response({
        'group': {'id': group.id, 'name': group.group_name, 'code': group.group_code, 'weekly_goal': float(group.weekly_goal), 'daily_contribution': float(group.daily_contribution)},
        'statistics': {'approved_members': approved_members.count(), 'pending_members': pending_members.count(), 'total_raised': float(total_raised), 'weekly_raised': float(weekly_total)},
        'pending_members': [{'id': m.id, 'username': m.user.username, 'email': m.user.email, 'phone': m.phone_number} for m in pending_members],
        'members': members_data
    })
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_admin_approve_member(request, member_id):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        member = Member.objects.get(id=member_id, group=group_admin.managed_group, status='pending')
    except (GroupAdmin.DoesNotExist, Member.DoesNotExist):
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    member.status = 'approved'
    member.approved_by = request.user
    member.save()
    return Response({'message': f'Member #{member.member_number} approved'})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_admin_reject_member(request, member_id):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        member = Member.objects.get(id=member_id, group=group_admin.managed_group, status='pending')
    except (GroupAdmin.DoesNotExist, Member.DoesNotExist):
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    member.status = 'rejected'
    member.save()
    return Response({'message': 'Member rejected'})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_admin_update_settings(request):
    try:
        group_admin = GroupAdmin.objects.get(user=request.user)
        group = group_admin.managed_group
    except GroupAdmin.DoesNotExist:
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    group.weekly_goal = request.data.get('weekly_goal', group.weekly_goal)
    group.daily_contribution = request.data.get('daily_contribution', group.daily_contribution)
    group.description = request.data.get('description', group.description)
    group.save()
    return Response({'message': 'Settings updated'})
# ==================== REGULAR USER VIEWS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    try:
        member = Member.objects.get(user=request.user, status='approved')
        group = member.group
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    weekly, _ = WeeklyProgress.objects.get_or_create(member=member, week_start_date=week_start, defaults={'week_end_date': week_start + timedelta(days=6), 'weekly_goal': group.weekly_goal})
    
    members = Member.objects.filter(group=group, status='approved')
    leaderboard = []
    for m in members:
        w = WeeklyProgress.objects.filter(member=m, week_start_date=week_start).first()
        leaderboard.append({'member_number': m.member_number, 'username': m.user.username, 'weekly_total': float(w.total_contributed) if w else 0})
    leaderboard.sort(key=lambda x: x['weekly_total'], reverse=True)
    
    your_rank = next((i+1 for i, m in enumerate(leaderboard) if m['member_number'] == member.member_number), len(leaderboard))
    recent = Contribution.objects.filter(member=member)[:10]
    
    return Response({
        'member': {'number': member.member_number, 'username': member.user.username, 'email': member.user.email, 'total_contributed': float(member.total_contributed), 'joined_at': member.joined_at},
        'group': {'name': group.group_name, 'code': group.group_code, 'weekly_goal': float(group.weekly_goal), 'daily_contribution': float(group.daily_contribution), 'days_left_in_week': max(0, 6 - today.weekday())},
        'weekly_progress': {'contributed': float(weekly.total_contributed), 'goal': float(group.weekly_goal), 'percentage': min(100, float(weekly.total_contributed) / float(group.weekly_goal) * 100) if group.weekly_goal > 0 else 0, 'remaining': max(0, float(group.weekly_goal) - float(weekly.total_contributed))},
        'daily_status': {'has_contributed_today': Contribution.objects.filter(member=member, date=today).exists()},
        'leaderboard': leaderboard, 'your_rank': your_rank,
        'ai_prediction': get_ai_prediction(member),
        'recent_contributions': [{'amount': float(c.amount), 'date': c.date.strftime('%Y-%m-%d'), 'transaction_id': c.transaction_id[:12]} for c in recent],
        'total_members': members.count()
    })
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_contribution(request):
    try:
        member = Member.objects.get(user=request.user, status='approved')
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    amount = Decimal(str(request.data.get('amount', 0)))
    if amount <= 0:
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
    
    contribution = Contribution.objects.create(member=member, group=member.group, amount=amount, transaction_id=f"MRF{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}")
    member.total_contributed += amount
    member.save()
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    weekly, _ = WeeklyProgress.objects.get_or_create(member=member, week_start_date=week_start, defaults={'week_end_date': week_start + timedelta(days=6), 'weekly_goal': member.group.weekly_goal})
    weekly.total_contributed += amount
    weekly.save()
    
    return Response({'message': f'Contributed KES {amount}!', 'amount': float(amount), 'new_total': float(member.total_contributed)})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_payment(request):
    phone = request.data.get('phone_number', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return Response({'success': True, 'message': f'STK Push sent to {phone}'})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_to_become_admin(request):
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    admin_request = AdminRequest.objects.create(requester=request.user, request_type='group_admin', status='pending')
    return Response({'message': 'Request sent to Super Admin', 'request_id': admin_request.id})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_to_create_group(request):
    admin_request = AdminRequest.objects.create(requester=request.user, request_type='create_group', group_name=request.data.get('group_name'), group_description=request.data.get('description', ''), status='pending')
    return Response({'message': 'Group creation request sent', 'request_id': admin_request.id})
