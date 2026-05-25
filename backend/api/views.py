from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from decimal import Decimal
import uuid
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, PasswordResetToken

# Helper
def get_ai_prediction(member):
    return {'predicted_total': float(member.total_contributed) * 1.15 if member.total_contributed > 0 else 115, 'confidence': 0.75, 'trend': 'improving', 'recommendation': 'Keep saving consistently!'}

# Health
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok', 'message': 'API running'})

# Register
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone = request.data.get('phone_number', '')
    group_code = request.data.get('group_code', '').upper()
    is_admin = request.data.get('is_admin', False)
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username exists'}, status=400)
    
    if is_admin:
        user = User.objects.create_user(username=username, password=password, email=email, is_staff=True)
        Member.objects.create(user=user, phone_number=phone, status='approved')
        GroupAdmin.objects.create(user=user)
        return Response({'message': 'Admin created! You can now create groups.'})
    
    if not group_code:
        return Response({'error': 'Group code required'}, status=400)
    
    try:
        group = ChamaGroup.objects.get(group_code=group_code, is_active=True)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Invalid group code'}, status=404)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    member = Member.objects.create(user=user, group=group, phone_number=phone, status='pending')
    
    return Response({'message': f'Registered! Waiting for approval to join {group.group_name}'})

# Login
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    role = 'user'
    if user.is_superuser:
        role = 'superadmin'
    elif user.is_staff:
        role = 'admin'
    
    return Response({'access': str(refresh.access_token), 'user': {'username': user.username, 'role': role}})

# ============ GROUP CRUD ============
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return Response({'error': 'Only admins can create groups'}, status=403)
    
    group = ChamaGroup.objects.create(
        group_name=request.data.get('group_name'),
        description=request.data.get('description', ''),
        weekly_goal=request.data.get('weekly_goal', 100),
        daily_contribution=request.data.get('daily_contribution', 10),
        created_by=request.user
    )
    
    GroupAdmin.objects.get_or_create(user=request.user, defaults={'managed_group': group})
    
    return Response({'message': f'Group "{group.group_name}" created!', 'group_code': group.group_code})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_groups(request):
    if request.user.is_superuser:
        groups = ChamaGroup.objects.all()
    else:
        try:
            admin = GroupAdmin.objects.get(user=request.user)
            groups = ChamaGroup.objects.filter(id=admin.managed_group.id) if admin.managed_group else []
        except GroupAdmin.DoesNotExist:
            groups = []
    
    data = [{'id': g.id, 'name': g.group_name, 'code': g.group_code, 'weekly_goal': float(g.weekly_goal), 'member_count': g.members.filter(status='approved').count()} for g in groups]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_group_detail(request, group_id):
    try:
        group = ChamaGroup.objects.get(id=group_id)
    except ChamaGroup.DoesNotExist:
        return Response({'error': 'Group not found'}, status=404)
    
    return Response({
        'id': group.id,
        'name': group.group_name,
        'code': group.group_code,
        'weekly_goal': float(group.weekly_goal),
        'daily_contribution': float(group.daily_contribution),
        'member_count': group.members.filter(status='approved').count(),
        'pending_members': [{'id': m.id, 'username': m.user.username, 'email': m.user.email} for m in group.members.filter(status='pending')],
        'members': [{'id': m.id, 'member_number': m.member_number, 'username': m.user.username, 'total_contributed': float(m.total_contributed)} for m in group.members.filter(status='approved')]
    })

# ============ MEMBER MANAGEMENT ============
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_member(request, member_id):
    try:
        member = Member.objects.get(id=member_id, status='pending')
        member.status = 'approved'
        member.save()
        return Response({'message': f'Member #{member.member_number} approved'})
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_member(request, member_id):
    try:
        member = Member.objects.get(id=member_id, status='pending')
        member.status = 'suspended'
        member.save()
        return Response({'message': 'Member rejected'})
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)

# ============ CONTRIBUTIONS ============
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
    
    contribution = Contribution.objects.create(
        member=member, group=member.group, amount=amount,
        transaction_id=f"MRF{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    )
    
    member.total_contributed += amount
    member.save()
    
    return Response({'message': f'Contributed KES {amount}!', 'new_total': float(member.total_contributed)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    try:
        member = Member.objects.get(user=request.user, status='approved')
        group = member.group
    except Member.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)
    
    return Response({
        'member': {'number': member.member_number, 'username': member.user.username, 'total_contributed': float(member.total_contributed)},
        'group': {'name': group.group_name, 'code': group.group_code, 'weekly_goal': float(group.weekly_goal), 'daily_contribution': float(group.daily_contribution)},
        'ai_prediction': get_ai_prediction(member)
    })

# ============ FORGOT PASSWORD ============
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_payment(request):
    phone = request.data.get('phone_number', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return Response({'success': True, 'message': f'STK Push sent to {phone}'})
