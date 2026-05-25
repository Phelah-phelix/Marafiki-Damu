from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
import uuid
from decimal import Decimal
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, AdminRequest

# Helper function
def get_ai_prediction(member):
    return {
        'predicted_total': float(member.total_contributed) * 1.15 if member.total_contributed > 0 else 115,
        'confidence': 0.75,
        'trend': 'improving',
        'recommendation': 'Keep saving consistently! You are doing great!'
    }

# ==================== REGISTRATION & LOGIN ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """User registers with group code"""
    print("="*50)
    print("REGISTRATION ATTEMPT")
    print("="*50)
    
    group_code = request.data.get('group_code', '').upper().strip()
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    
    print(f"Group code received: {group_code}")
    print(f"Username: {username}")
    print(f"Email: {email}")
    
    # Validate group code
    try:
        group = ChamaGroup.objects.get(group_code=group_code, is_active=True)
        print(f"✅ Group found: {group.group_name}")
    except ChamaGroup.DoesNotExist:
        print(f"❌ Group not found with code: {group_code}")
        # List available groups for debugging
        available = ChamaGroup.objects.filter(is_active=True)
        print(f"Available groups: {[g.group_code for g in available]}")
        return Response({'error': f'Invalid group code: {group_code}'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if username exists
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check group capacity
    member_count = Member.objects.filter(group=group, status='approved').count()
    if group.max_members and member_count >= group.max_members:
        return Response({'error': f'Group {group.group_name} is full'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create user
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=request.data.get('first_name', ''),
        last_name=request.data.get('last_name', '')
    )
    
    # Create member
    member = Member.objects.create(
        user=user,
        group=group,
        phone_number=phone_number,
        id_number=request.data.get('id_number', ''),
        location=request.data.get('location', ''),
        occupation=request.data.get('occupation', ''),
        status='pending'
    )
    
    print(f"✅ Member created: {member.user.username} for group {group.group_name}")
    
    return Response({
        'message': f'Successfully registered! Your request to join {group.group_name} has been sent. Wait for admin approval.',
        'group_name': group.group_name,
        'status': 'pending'
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login user and determine role"""
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
            'refresh': str(refresh),
            'user': {'id': user.id, 'username': user.username, 'role': 'superadmin'}
        })
    
    # Check if Group Admin
    try:
        group_admin = GroupAdmin.objects.get(user=user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': 'group_admin',
                'group_id': group_admin.managed_group.id,
                'group_name': group_admin.managed_group.group_name
            }
        })
    except GroupAdmin.DoesNotExist:
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
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': 'member',
                'member_number': member.member_number,
                'group_id': member.group.id,
                'group_name': member.group.group_name
            }
        })
    except Member.DoesNotExist:
        return Response({'error': 'No profile found'}, status=status.HTTP_404_NOT_FOUND)

# ==================== SUPER ADMIN FUNCTIONS ====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
def superadmin_create_group(request):
    """Super Admin creates a group"""
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

@api_view(['GET'])
@permission_classes([IsAdminUser])
def superadmin_get_all_groups(request):
    groups = ChamaGroup.objects.all()
    data = []
    for group in groups:
        admin = GroupAdmin.objects.filter(managed_group=group).first()
        data.append({
            'id': group.id,
            'name': group.group_name,
            'code': group.group_code,
            'member_count': Member.objects.filter(group=group, status='approved').count(),
            'admin_name': admin.user.username if admin else 'No admin',
            'is_active': group.is_active
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def superadmin_get_pending_requests(request):
    requests = AdminRequest.objects.filter(status='pending')
    data = [{
        'id': r.id,
        'requester': r.requester.username,
        'requester_email': r.requester.email,
        'request_type': r.request_type,
        'group_name': r.group_name,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in requests]
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def superadmin_approve_admin_request(request, request_id):
    try:
        admin_request = AdminRequest.objects.get(id=request_id, status='pending')
    except AdminRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if admin_request.request_type == 'create_group':
        group = ChamaGroup.objects.create(
            group_name=admin_request.group_name,
            description=admin_request.group_description,
            weekly_goal=100,
            daily_contribution=10,
            is_active=True,
            created_by=request.user
        )
    else:
        group_id = request.data.get('group_id')
        try:
            group = ChamaGroup.objects.get(id=group_id)
        except ChamaGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    user = admin_request.requester
    user.is_staff = True
    user.save()
    
    GroupAdmin.objects.create(
        user=user,
        managed_group=group,
        assigned_by=request.user
    )
    
    admin_request.status = 'approved'
    admin_request.reviewed_by = request.user
    admin_request.reviewed_at = timezone.now()
    admin_request.save()
    
    return Response({'message': f'Admin request approved for {user.username}', 'group_code': group.group_code})

@api_view(['POST'])
@permission_classes([IsAdminUser])
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

@api_view(['POST'])
@permission_classes([IsAdminUser])
def superadmin_assign_group_admin(request):
    username = request.data.get('username')
    group_id = request.data.get('group_id')
    
    try:
        user = User.objects.get(username=username)
        group = ChamaGroup.objects.get(id=group_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    user.is_staff = True
    user.save()
    
    group_admin, created = GroupAdmin.objects.get_or_create(
        user=user,
        defaults={'managed_group': group, 'assigned_by': request.user}
    )
    
    if not created:
        group_admin.managed_group = group
        group_admin.save()
    
    return Response({'message': f'{username} is now admin for {group.group_name}'})

# ==================== GROUP ADMIN FUNCTIONS ====================

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
    
    members_data = []
    for member in members:
        members_data.append({
            'id': member.id,
            'member_number': member.member_number,
            'username': member.user.username,
            'email': member.user.email,
            'phone': member.phone_number,
            'status': member.status,
            'total_contributed': float(member.total_contributed)
        })
    
    return Response({
        'group': {
            'id': group.id,
            'name': group.group_name,
            'code': group.group_code,
            'weekly_goal': float(group.weekly_goal),
            'daily_contribution': float(group.daily_contribution)
        },
        'statistics': {
            'approved_members': approved_members.count(),
            'pending_members': pending_members.count(),
            'total_raised': float(total_raised),
            'weekly_raised': float(weekly_total)
        },
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

# ==================== USER FUNCTIONS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
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
        transaction_id=f"MARAFIKI_{uuid.uuid4().hex[:12].upper()}"
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
    user = request.user
    try:
        member = Member.objects.get(user=user)
    except Member.DoesNotExist:
        return Response({'error': 'You must be a member first'}, status=status.HTTP_400_BAD_REQUEST)
    
    admin_request = AdminRequest.objects.create(
        requester=user,
        request_type='group_admin',
        status='pending'
    )
    
    return Response({'message': 'Request sent to Super Admin', 'request_id': admin_request.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_to_create_group(request):
    admin_request = AdminRequest.objects.create(
        requester=request.user,
        request_type='create_group',
        group_name=request.data.get('group_name'),
        group_description=request.data.get('description', ''),
        status='pending'
    )
    
    return Response({'message': 'Group creation request sent', 'request_id': admin_request.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_contribution(request):
    try:
        member = Member.objects.get(user=request.user)
        if member.status != 'approved':
            return Response({'error': 'Account not approved yet'}, status=status.HTTP_403_FORBIDDEN)
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    
    amount = Decimal(str(request.data.get('amount', 0)))
    
    if amount <= 0:
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate unique transaction ID
    transaction_id = f"MRF{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    
    # Record contribution
    contribution = Contribution.objects.create(
        member=member,
        group=member.group,
        amount=amount,
        transaction_id=transaction_id,
        payment_method=request.data.get('payment_method', 'M-Pesa'),
        date=timezone.now().date()
    )
    
    # Update member total
    member.total_contributed += amount
    member.save()
    
    # Update weekly progress
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    weekly, created = WeeklyProgress.objects.get_or_create(
        member=member,
        week_start_date=week_start,
        defaults={
            'week_end_date': week_end,
            'weekly_goal': member.group.weekly_goal,
            'total_contributed': amount,
            'group': member.group
        }
    )
    
    if not created:
        weekly.total_contributed += amount
        weekly.is_completed = weekly.total_contributed >= weekly.weekly_goal
        weekly.save()
    
    print(f"✅ Contribution recorded: {member.user.username} added KES {amount}")
    
    return Response({
        'message': 'Contribution recorded successfully!',
        'transaction_id': transaction_id,
        'amount': float(amount),
        'new_total': float(member.total_contributed),
        'weekly_total': float(weekly.total_contributed),
        'weekly_goal': float(weekly.weekly_goal),
        'percentage': min(100, float(weekly.total_contributed) / float(weekly.weekly_goal) * 100) if weekly.weekly_goal > 0 else 0
    })

# ==================== M-PESA STK PUSH IMPLEMENTATION ====================

from .mpesa_config import MpesaSTKPush
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

# Initialize M-Pesa
mpesa_client = MpesaSTKPush()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_stk_push(request):
    """Initiate M-Pesa STK Push payment"""
    try:
        member = Member.objects.get(user=request.user)
        amount = request.data.get('amount')
        phone_number = request.data.get('phone_number')
        
        if not amount or not phone_number:
            return Response({
                'success': False,
                'message': 'Amount and phone number are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate unique transaction reference
        transaction_ref = f"MARAFIKI{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        
        # Send STK Push
        result = mpesa_client.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"MRF{member.member_number}",
            transaction_desc=f"Marafiki Damu Contribution - Member #{member.member_number}"
        )
        
        if result['success']:
            # Store checkout request ID for later verification
            request.session['checkout_request_id'] = result.get('checkout_request_id')
            
            return Response({
                'success': True,
                'message': 'STK Push sent to your phone. Please enter your PIN to complete payment.',
                'checkout_request_id': result.get('checkout_request_id'),
                'merchant_request_id': result.get('merchant_request_id')
            })
        else:
            return Response({
                'success': False,
                'message': result.get('message', 'Failed to send STK Push')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Member.DoesNotExist:
        return Response({'success': False, 'message': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def mpesa_callback(request):
    """M-Pesa callback URL to receive payment confirmation"""
    try:
        callback_data = json.loads(request.body)
        print(f"📥 M-Pesa Callback Received: {callback_data}")
        
        # Extract payment details
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
        checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        amount = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
        
        # Extract amount from metadata
        payment_amount = 0
        for item in amount:
            if item.get('Name') == 'Amount':
                payment_amount = item.get('Value', 0)
        
        if result_code == 0:
            # Payment successful
            print(f"✅ Payment successful: KES {payment_amount}")
            
            # Here you would record the contribution in your database
            # You need to associate this with a member using checkout_request_id
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        else:
            print(f"❌ Payment failed: {result_desc}")
            return JsonResponse({'ResultCode': result_code, 'ResultDesc': result_desc})
            
    except Exception as e:
        print(f"❌ Callback error: {e}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': str(e)})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def query_payment_status(request):
    """Query the status of a pending STK Push payment"""
    checkout_request_id = request.data.get('checkout_request_id')
    
    if not checkout_request_id:
        return Response({'success': False, 'message': 'Checkout request ID required'})
    
    result = mpesa_client.query_status(checkout_request_id)
    
    if result['success']:
        return Response({
            'success': True,
            'result_code': result.get('result_code'),
            'result_desc': result.get('result_desc')
        })
    else:
        return Response({
            'success': False,
            'message': result.get('message', 'Failed to query status')
        })
