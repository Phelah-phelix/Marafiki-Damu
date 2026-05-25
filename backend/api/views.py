from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
import uuid
from decimal import Decimal
from .models import ChamaGroup, Member, Contribution, WeeklyProgress

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

# Register User - Admin can register without group code
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    group_code = request.data.get('group_code', '').upper().strip()
    is_admin_request = request.data.get('is_admin', False)
    
    # Check if user exists
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)
    
    # For Admin registration (Superuser or Group Admin) - NO GROUP CODE NEEDED
    if is_admin_request:
        # Create user as staff (admin)
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            is_staff=True
        )
        
        # Create member record (no group required for admin)
        member = Member.objects.create(
            user=user,
            phone_number=phone_number,
            status='approved',  # Auto-approve admin accounts
            is_group_admin=True
        )
        
        return Response({
            'message': 'Admin account created successfully! You can now login.',
            'user_id': user.id,
            'is_admin': True
        }, status=status.HTTP_201_CREATED)
    
    # Regular User Registration - REQUIRES GROUP CODE
    if not group_code:
        return Response({'error': 'Group code is required for regular users'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        group = ChamaGroup.objects.get(group_code=group_code, is_active=True)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Invalid group code'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check group capacity
    member_count = Member.objects.filter(group=group, status='approved').count()
    if group.max_members and member_count >= group.max_members:
        return Response({'error': f'Group {group.group_name} is full'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create regular user
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email
    )
    
    # Create member with pending approval
    member = Member.objects.create(
        user=user,
        group=group,
        phone_number=phone_number,
        status='pending',
        is_group_admin=False
    )
    
    return Response({
        'message': f'Registration successful! Your request to join {group.group_name} has been sent. Wait for admin approval.',
        'group_name': group.group_name,
        'status': 'pending'
    }, status=status.HTTP_201_CREATED)

# Login User
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    # Check if Super Admin
    if user.is_superuser:
        return Response({
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': 'superadmin',
                'is_admin': True
            }
        })
    
    # Check if Group Admin
    try:
        member = Member.objects.get(user=user)
        if member.is_group_admin or user.is_staff:
            return Response({
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': 'group_admin',
                    'group_id': member.group.id if member.group else None,
                    'group_name': member.group.group_name if member.group else 'No Group',
                    'is_admin': True
                }
            })
    except Member.DoesNotExist:
        pass
    
    # Check if Regular Member
    try:
        member = Member.objects.get(user=user)
        if member.status != 'approved':
            return Response({
                'error': f'Account pending approval for {member.group.group_name}',
                'status': member.status
            }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': 'member',
                'member_number': member.member_number,
                'group_id': member.group.id,
                'group_name': member.group.group_name,
                'is_admin': False
            }
        })
    except Member.DoesNotExist:
        return Response({'error': 'No profile found'}, status=status.HTTP_404_NOT_FOUND)

# Create Super Admin (First time setup)
@api_view(['POST'])
@permission_classes([AllowAny])
def create_super_admin(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    
    if User.objects.filter(is_superuser=True).exists():
        return Response({'error': 'Super admin already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.create_superuser(
        username=username,
        password=password,
        email=email
    )
    
    return Response({
        'message': 'Super admin created successfully!',
        'username': username
    })

# User Dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    try:
        member = Member.objects.get(user=request.user)
        if not member.group:
            return Response({'error': 'No group assigned'}, status=status.HTTP_400_BAD_REQUEST)
        group = member.group
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    weekly, _ = WeeklyProgress.objects.get_or_create(
        member=member, week_start_date=week_start,
        defaults={'week_end_date': week_start + timedelta(days=6), 'weekly_goal': group.weekly_goal}
    )
    
    members = Member.objects.filter(group=group, status='approved')
    leaderboard = []
    for m in members:
        w = WeeklyProgress.objects.filter(member=m, week_start_date=week_start).first()
        leaderboard.append({
            'member_number': m.member_number,
            'username': m.user.username,
            'weekly_total': float(w.total_contributed) if w else 0
        })
    leaderboard.sort(key=lambda x: x['weekly_total'], reverse=True)
    
    your_rank = next((i+1 for i, m in enumerate(leaderboard) if m['member_number'] == member.member_number), len(leaderboard))
    recent = Contribution.objects.filter(member=member)[:10]
    
    return Response({
        'member': {
            'number': member.member_number,
            'username': member.user.username,
            'email': member.user.email,
            'total_contributed': float(member.total_contributed),
            'joined_at': member.joined_at
        },
        'group': {
            'name': group.group_name,
            'code': group.group_code,
            'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution),
            'days_left_in_week': max(0, 6 - today.weekday())
        },
        'weekly_progress': {
            'contributed': float(weekly.total_contributed),
            'goal': float(group.weekly_goal),
            'percentage': min(100, float(weekly.total_contributed) / float(group.weekly_goal) * 100) if group.weekly_goal > 0 else 0,
            'remaining': max(0, float(group.weekly_goal) - float(weekly.total_contributed))
        },
        'daily_status': {'has_contributed_today': Contribution.objects.filter(member=member, date=today).exists()},
        'leaderboard': leaderboard,
        'your_rank': your_rank,
        'ai_prediction': get_ai_prediction(member),
        'recent_contributions': [{'amount': float(c.amount), 'date': c.date.strftime('%Y-%m-%d'), 'transaction_id': c.transaction_id[:12]} for c in recent],
        'total_members': members.count()
    })

# Add Contribution
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_contribution(request):
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    amount = Decimal(str(request.data.get('amount', 0)))
    
    if amount <= 0:
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
    
    contribution = Contribution.objects.create(
        member=member,
        group=member.group,
        amount=amount,
        transaction_id=f"MRF{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    )
    
    member.total_contributed += amount
    member.save()
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    weekly, _ = WeeklyProgress.objects.get_or_create(
        member=member, week_start_date=week_start,
        defaults={'week_end_date': week_start + timedelta(days=6), 'weekly_goal': member.group.weekly_goal}
    )
    weekly.total_contributed += amount
    weekly.save()
    
    return Response({'message': f'Contributed KES {amount}!', 'amount': float(amount), 'new_total': float(member.total_contributed)})

# M-Pesa Simulation
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_payment(request):
    phone = request.data.get('phone_number', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return Response({'success': True, 'message': f'STK Push sent to {phone}'})

# ==================== SUPER ADMIN VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_get_all_groups(request):
    """Super Admin can see ALL groups created by any admin"""
    groups = ChamaGroup.objects.all().order_by('-created_at')
    data = []
    for group in groups:
        admin = GroupAdmin.objects.filter(managed_group=group).first()
        data.append({
            'id': group.id,
            'name': group.group_name,
            'code': group.group_code,
            'description': group.description,
            'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution),
            'member_count': Member.objects.filter(group=group, status='approved').count(),
            'pending_count': Member.objects.filter(group=group, status='pending').count(),
            'admin_name': admin.user.username if admin else 'No admin',
            'admin_id': admin.user.id if admin else None,
            'is_active': group.is_active,
            'created_at': group.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_create_group(request):
    """Super Admin creates a new group and generates invite code"""
    group = ChamaGroup.objects.create(
        group_name=request.data.get('group_name'),
        description=request.data.get('description', ''),
        weekly_goal=request.data.get('weekly_goal', 100),
        daily_contribution=request.data.get('daily_contribution', 10),
        max_members=request.data.get('max_members', 50),
        is_active=True,
        created_by=request.user
    )
    return Response({
        'message': f'Group "{group.group_name}" created!',
        'group_code': group.group_code,
        'group_id': group.id
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def superadmin_assign_group_admin(request):
    """Super Admin assigns a user as admin for a specific group"""
    username = request.data.get('username')
    group_id = request.data.get('group_id')
    
    try:
        user = User.objects.get(username=username)
        group = ChamaGroup.objects.get(id=group_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Make user staff
    user.is_staff = True
    user.save()
    
    # Create or update group admin
    group_admin, created = GroupAdmin.objects.get_or_create(
        user=user,
        defaults={'managed_group': group, 'assigned_by': request.user}
    )
    if not created:
        group_admin.managed_group = group
        group_admin.assigned_by = request.user
        group_admin.save()
    
    return Response({
        'message': f'{username} is now admin of {group.group_name}',
        'group_code': group.group_code
    })


# ==================== GROUP ADMIN VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsGroupAdmin])
def group_admin_create_group(request):
    """Group Admin creates a new group (they become admin of this group)"""
    group = ChamaGroup.objects.create(
        group_name=request.data.get('group_name'),
        description=request.data.get('description', ''),
        weekly_goal=request.data.get('weekly_goal', 100),
        daily_contribution=request.data.get('daily_contribution', 10),
        max_members=request.data.get('max_members', 50),
        is_active=True,
        created_by=request.user
    )
    
    # Auto-assign this admin to the new group
    group_admin, created = GroupAdmin.objects.get_or_create(
        user=request.user,
        defaults={'managed_group': group, 'assigned_by': request.user}
    )
    
    return Response({
        'message': f'Group "{group.group_name}" created!',
        'group_code': group.group_code,
        'group_id': group.id
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsGroupAdmin])
def group_admin_get_my_groups(request):
    """Group Admin sees all groups they manage"""
    group_admins = GroupAdmin.objects.filter(user=request.user)
    data = []
    for ga in group_admins:
        group = ga.managed_group
        data.append({
            'id': group.id,
            'name': group.group_name,
            'code': group.group_code,
            'description': group.description,
            'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution),
            'member_count': Member.objects.filter(group=group, status='approved').count(),
            'pending_count': Member.objects.filter(group=group, status='pending').count(),
            'is_active': group.is_active
        })
    return Response(data)


# ==================== REGULAR USER VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsGroupMember])
def user_dashboard(request):
    """Regular user dashboard"""
    try:
        member = Member.objects.get(user=request.user)
        group = member.group
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    weekly, _ = WeeklyProgress.objects.get_or_create(
        member=member, week_start_date=week_start,
        defaults={'week_end_date': week_start + timedelta(days=6), 'weekly_goal': group.weekly_goal}
    )
    
    members = Member.objects.filter(group=group, status='approved')
    leaderboard = []
    for m in members:
        w = WeeklyProgress.objects.filter(member=m, week_start_date=week_start).first()
        leaderboard.append({
            'member_number': m.member_number,
            'username': m.user.username,
            'weekly_total': float(w.total_contributed) if w else 0
        })
    leaderboard.sort(key=lambda x: x['weekly_total'], reverse=True)
    
    your_rank = next((i+1 for i, m in enumerate(leaderboard) if m['member_number'] == member.member_number), len(leaderboard))
    recent = Contribution.objects.filter(member=member)[:10]
    
    return Response({
        'member': {
            'number': member.member_number,
            'username': member.user.username,
            'email': member.user.email,
            'total_contributed': float(member.total_contributed),
            'joined_at': member.joined_at
        },
        'group': {
            'id': group.id,
            'name': group.group_name,
            'code': group.group_code,
            'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution),
            'days_left_in_week': max(0, 6 - today.weekday())
        },
        'weekly_progress': {
            'contributed': float(weekly.total_contributed),
            'goal': float(group.weekly_goal),
            'percentage': min(100, float(weekly.total_contributed) / float(group.weekly_goal) * 100) if group.weekly_goal > 0 else 0,
            'remaining': max(0, float(group.weekly_goal) - float(weekly.total_contributed))
        },
        'daily_status': {'has_contributed_today': Contribution.objects.filter(member=member, date=today).exists()},
        'leaderboard': leaderboard,
        'your_rank': your_rank,
        'ai_prediction': get_ai_prediction(member),
        'recent_contributions': [{'amount': float(c.amount), 'date': c.date.strftime('%Y-%m-%d'), 'transaction_id': c.transaction_id[:12]} for c in recent],
        'total_members': members.count()
    })
