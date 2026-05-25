from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import secrets
import string

class ChamaGroup(models.Model):
    group_name = models.CharField(max_length=100, unique=True)
    group_code = models.CharField(max_length=10, unique=True, blank=True)
    description = models.TextField(blank=True)
    weekly_goal = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    daily_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    max_members = models.IntegerField(default=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.group_code:
            self.group_code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(6))
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.group_name} ({self.group_code})"

class GroupAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='group_admin_profile')
    managed_group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='admins')
    can_approve_members = models.BooleanField(default=True)
    can_edit_settings = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_admins')
    
    def __str__(self):
        return f"Admin: {self.user.username} → {self.managed_group.group_name}"

class Member(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Active'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    member_number = models.IntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    id_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_group_admin = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_members')
    approved_at = models.DateTimeField(null=True, blank=True)
    total_contributed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.status == 'approved' and self.member_number is None and self.group:
            last_member = Member.objects.filter(group=self.group, status='approved').order_by('-member_number').first()
            self.member_number = (last_member.member_number + 1) if last_member else 1
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"#{self.member_number or '?'} - {self.user.username}"

class Contribution(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='contributions', null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, default='M-Pesa')
    is_verified = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.group and self.member:
            self.group = self.member.group
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-date', '-created_at']

class WeeklyProgress(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='weekly_progress')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='weekly_progress', null=True)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    total_contributed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weekly_goal = models.DecimalField(max_digits=10, decimal_places=2)
    is_completed = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.group and self.member:
            self.group = self.member.group
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['member', 'week_start_date']

class AdminRequest(models.Model):
    REQUEST_TYPES = [
        ('group_admin', 'Group Admin Request'),
        ('create_group', 'Create Group Request'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    group_name = models.CharField(max_length=100, blank=True, null=True)
    group_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.requester.username} - {self.request_type} - {self.status}"

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.token:
            alphabet = string.ascii_letters + string.digits
            self.token = ''.join(secrets.choice(alphabet) for _ in range(50))
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

class AI_Prediction(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='predictions')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, null=True)
    prediction_date = models.DateTimeField(auto_now_add=True)
    predicted_future_total = models.DecimalField(max_digits=12, decimal_places=2)
    confidence_score = models.FloatField()
    trend = models.CharField(max_length=20)
    recommendation = models.TextField()
    
    def save(self, *args, **kwargs):
        if not self.group and self.member:
            self.group = self.member.group
        super().save(*args, **kwargs)
