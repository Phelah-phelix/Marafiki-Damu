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
    
    def save(self, *args, **kwargs):
        if not self.group_code:
            self.group_code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(6))
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.group_name} ({self.group_code})"

class GroupAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='group_admin_profile')
    managed_group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='admins', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Admin: {self.user.username}"

class Member(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Active'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    member_number = models.IntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_contributed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.status == 'approved' and self.member_number is None and self.group:
            last_member = Member.objects.filter(group=self.group, status='approved').order_by('-member_number').first()
            self.member_number = (last_member.member_number + 1) if last_member else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"#{self.member_number or '?'} - {self.user.username}"

class Contribution(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='contributions', null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    transaction_id = models.CharField(max_length=100, unique=True)
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
    
    class Meta:
        unique_together = ['member', 'week_start_date']

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

class GroupInviteToken(models.Model):
    """Unique invite tokens for group members"""
    group = models.ForeignKey(ChamaGroup, on_delete=models.CASCADE, related_name='invite_tokens')
    token = models.CharField(max_length=10, unique=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invites')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(default=1)
    used_count = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        if not self.token:
            # Generate unique 8-character token
            import secrets
            import string
            alphabet = string.ascii_uppercase + string.digits
            self.token = ''.join(secrets.choice(alphabet) for _ in range(8))
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return self.is_active and (self.expires_at is None or timezone.now() < self.expires_at) and (self.used_count < self.max_uses)
    
    def __str__(self):
        return f"{self.token} - {self.group.group_name}"
